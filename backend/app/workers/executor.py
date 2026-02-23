from __future__ import annotations

import json
import logging
import os
import queue
import socket
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import run_duration_seconds, runs_failed_total, runs_total, worker_heartbeat
from app.db.session import SessionLocal
from app.models.artifact import Artifact
from app.models.robot import ArtifactType, EntryPointType, RobotVersion
from app.models.run import Run, RunLog, RunStatus
from app.services.queue_service import get_run_log_channel, get_sync_redis, refresh_queue_depth_sync

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger("enesa.worker")
worker_name = f"{socket.gethostname()}:{os.getpid()}"


@dataclass(slots=True)
class StreamLine:
    level: str
    message: str


@dataclass(slots=True)
class ExecutionPlan:
    command: list[str]
    working_directory: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def append_log(db: Session, run_id: UUID, level: str, message: str) -> None:
    timestamp = utcnow()
    db.add(
        RunLog(
            run_id=run_id,
            timestamp=timestamp,
            level=level,
            message=message,
        )
    )
    db.commit()

    redis = get_sync_redis()
    redis.publish(
        get_run_log_channel(str(run_id)),
        json.dumps(
            {
                "run_id": str(run_id),
                "timestamp": timestamp.isoformat(),
                "level": level,
                "message": message,
            }
        ),
    )


def make_environment(version: RobotVersion, runtime_env: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(version.env_vars or {})
    env.update(runtime_env or {})
    return env


def stream_to_queue(stream, level: str, output: queue.Queue[StreamLine]) -> None:
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            output.put(StreamLine(level=level, message=line.rstrip("\n")))
    finally:
        stream.close()


def register_artifacts(db: Session, run: Run, run_dir: Path) -> None:
    if not run_dir.exists():
        return

    for file_path in run_dir.rglob("*"):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        db.add(
            Artifact(
                run_id=run.run_id,
                artifact_name=file_path.name,
                file_path=str(file_path.resolve()),
                file_size_bytes=stat.st_size,
                content_type=None,
            )
        )
    db.commit()


def finalize_metrics(run: Run) -> None:
    runs_total.inc()
    if run.status == RunStatus.FAILED.value:
        runs_failed_total.inc()
    if run.duration_seconds is not None:
        run_duration_seconds.observe(run.duration_seconds)


def _extract_zip_to_workspace(artifact_path: Path, workspace_dir: Path) -> None:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifact_path, "r") as zip_ref:
        zip_ref.extractall(workspace_dir)


def _resolve_execution_plan(version: RobotVersion, run_dir: Path, runtime_arguments: list[str]) -> ExecutionPlan:
    artifact_path = Path(version.artifact_path or "")
    if artifact_path and not artifact_path.is_absolute():
        artifact_path = Path(settings.artifacts_root) / artifact_path
    if not artifact_path.exists():
        raise ValueError(f"Version artifact not found: {artifact_path}")

    base_arguments = version.arguments or []
    final_arguments = [*base_arguments, *runtime_arguments]

    if version.artifact_type == ArtifactType.EXE.value:
        command = [str(artifact_path), *final_arguments]
        working_directory = version.working_directory or str(artifact_path.parent)
        return ExecutionPlan(command=command, working_directory=working_directory)

    if version.artifact_type == ArtifactType.ZIP.value:
        workspace_dir = run_dir / "workspace"
        _extract_zip_to_workspace(artifact_path=artifact_path, workspace_dir=workspace_dir)

        entrypoint = workspace_dir / version.entrypoint_path
        if not entrypoint.exists():
            raise ValueError(f"Entrypoint not found inside ZIP workspace: {entrypoint}")

        if version.entrypoint_type == EntryPointType.EXE.value or entrypoint.suffix.lower() == ".exe":
            command = [str(entrypoint), *final_arguments]
        else:
            command = [settings.python_executable, str(entrypoint), *final_arguments]

        working_directory = version.working_directory or str(workspace_dir)
        return ExecutionPlan(command=command, working_directory=working_directory)

    raise ValueError(f"Unsupported artifact_type: {version.artifact_type}")


def process_run(payload: dict[str, Any]) -> None:
    run_id = UUID(payload["run_id"])
    runtime_arguments = payload.get("runtime_arguments", [])
    runtime_env = payload.get("runtime_env", {})

    db = SessionLocal()
    try:
        run = db.scalar(select(Run).where(Run.run_id == run_id))
        if not run:
            logger.error("Run %s not found", run_id)
            return

        version = db.scalar(select(RobotVersion).where(RobotVersion.id == run.robot_version_id))
        if not version:
            run.status = RunStatus.FAILED.value
            run.error_message = "Robot version not found."
            run.finished_at = utcnow()
            db.commit()
            append_log(db, run_id, "ERROR", "Robot version not found for execution.")
            finalize_metrics(run)
            return

        run.status = RunStatus.RUNNING.value
        run.started_at = utcnow()
        run.host_name = socket.gethostname()
        db.commit()

        run_dir = Path(settings.artifacts_root) / "runs" / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = run_dir / "run.log"

        append_log(db, run_id, "INFO", "Execution started.")
        append_log(db, run_id, "INFO", f"Using robot version {version.version} ({version.id})")

        plan = _resolve_execution_plan(version=version, run_dir=run_dir, runtime_arguments=runtime_arguments)
        env = make_environment(version=version, runtime_env=runtime_env)

        append_log(db, run_id, "INFO", f"Command: {' '.join(plan.command)}")
        append_log(db, run_id, "INFO", f"Working directory: {plan.working_directory}")

        process = subprocess.Popen(
            plan.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=plan.working_directory,
            env=env,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        run.process_id = process.pid
        db.commit()

        line_queue: queue.Queue[StreamLine] = queue.Queue()
        stdout_thread = threading.Thread(target=stream_to_queue, args=(process.stdout, "INFO", line_queue), daemon=True)
        stderr_thread = threading.Thread(target=stream_to_queue, args=(process.stderr, "ERROR", line_queue), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        with log_file_path.open("a", encoding="utf-8") as log_file:
            while True:
                try:
                    item = line_queue.get(timeout=0.2)
                    append_log(db, run_id, item.level, item.message)
                    log_file.write(f"{utcnow().isoformat()} [{item.level}] {item.message}\n")
                    log_file.flush()
                except queue.Empty:
                    pass

                if process.poll() is not None and line_queue.empty() and not stdout_thread.is_alive() and not stderr_thread.is_alive():
                    break

        return_code = process.wait()
        finished_at = utcnow()
        run.finished_at = finished_at
        run.duration_seconds = (finished_at - (run.started_at or finished_at)).total_seconds()

        if return_code == 0:
            run.status = RunStatus.SUCCESS.value
            run.error_message = None
            append_log(db, run_id, "INFO", "Execution finished successfully.")
        else:
            run.status = RunStatus.FAILED.value
            run.error_message = f"Process returned exit code {return_code}"
            append_log(db, run_id, "ERROR", run.error_message)

        db.commit()
        register_artifacts(db=db, run=run, run_dir=run_dir)
        finalize_metrics(run)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure executing run %s", payload.get("run_id"))
        run = db.scalar(select(Run).where(Run.run_id == run_id))
        if run:
            finished_at = utcnow()
            run.status = RunStatus.FAILED.value
            run.finished_at = finished_at
            run.duration_seconds = (finished_at - run.started_at).total_seconds() if run.started_at else None
            run.error_message = str(exc)
            db.commit()
            append_log(db, run_id, "ERROR", f"Unexpected failure: {exc}")
            finalize_metrics(run)
    finally:
        db.close()


def run_worker() -> None:
    redis = get_sync_redis()
    queue_name = settings.redis_queue_name
    logger.info("Worker started, listening queue=%s", queue_name)

    while True:
        worker_heartbeat.labels(worker=worker_name).set(time.time())
        refresh_queue_depth_sync()
        item = redis.brpop(queue_name, timeout=5)
        if not item:
            continue

        _, raw_payload = item
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.error("Invalid payload from queue: %s", raw_payload)
            continue

        process_run(payload)


if __name__ == "__main__":
    run_worker()
