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
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import run_duration_seconds, runs_failed_total, runs_total, worker_heartbeat
from app.db.session import SessionLocal
from app.models.artifact import Artifact
from app.models.robot import ArtifactType, EntryPointType, RobotVersion
from app.models.run import Run, RunLog, RunStatus
from app.models.scheduler import Schedule, TriggerType
from app.models.worker import WorkerStatus
from app.services.queue_service import get_run_log_channel, get_sync_redis, refresh_queue_depth_sync, register_worker_heartbeat
from app.services.robot_env_service import resolve_runtime_env
from app.services.worker_service import get_worker, set_worker_status, upsert_worker_heartbeat

try:
    import psutil
except Exception:  # noqa: BLE001
    psutil = None

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger("enesa.worker")
worker_name = f"{socket.gethostname()}:{os.getpid()}"
worker_id = UUID(os.getenv("ENESA_WORKER_ID", str(uuid4())))
worker_version = os.getenv("ENESA_WORKER_VERSION", "2.0.0")


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


def _mark_worker_running() -> None:
    db = SessionLocal()
    try:
        upsert_worker_heartbeat(
            db=db,
            worker_id=worker_id,
            hostname=socket.gethostname(),
            version=worker_version,
            status_if_new=WorkerStatus.RUNNING.value,
        )
    finally:
        db.close()


def _mark_worker_stopped() -> None:
    db = SessionLocal()
    try:
        existing = get_worker(db=db, worker_id=worker_id)
        if existing:
            set_worker_status(db=db, worker_id=worker_id, status=WorkerStatus.STOPPED.value)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to mark worker as STOPPED")
    finally:
        db.close()


def _touch_worker_heartbeat() -> str:
    db = SessionLocal()
    try:
        worker = upsert_worker_heartbeat(
            db=db,
            worker_id=worker_id,
            hostname=socket.gethostname(),
            version=worker_version,
            status_if_new=WorkerStatus.RUNNING.value,
        )
        return worker.status
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist worker heartbeat")
        return WorkerStatus.RUNNING.value
    finally:
        db.close()


def _read_worker_status() -> str:
    db = SessionLocal()
    try:
        worker = get_worker(db=db, worker_id=worker_id)
        if not worker:
            worker = upsert_worker_heartbeat(
                db=db,
                worker_id=worker_id,
                hostname=socket.gethostname(),
                version=worker_version,
                status_if_new=WorkerStatus.RUNNING.value,
            )
        return worker.status
    except Exception:  # noqa: BLE001
        logger.exception("Failed to read worker status")
        return WorkerStatus.RUNNING.value
    finally:
        db.close()


def _terminate_process_tree(process: subprocess.Popen[str], grace_seconds: float = 5.0) -> None:
    if process.poll() is not None:
        return

    if psutil is not None:
        try:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()
            _, alive = psutil.wait_procs([*children, parent], timeout=grace_seconds)
            for node in alive:
                node.kill()
            return
        except Exception:  # noqa: BLE001
            logger.warning("Failed to terminate process tree with psutil for pid=%s. Falling back.", process.pid)

    try:
        process.terminate()
        process.wait(timeout=grace_seconds)
    except Exception:  # noqa: BLE001
        process.kill()


def _is_cancel_requested(db: Session, run: Run) -> bool:
    db.refresh(run, attribute_names=["cancel_requested", "status"])
    return bool(run.cancel_requested and run.status == RunStatus.RUNNING.value)


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

        schedule = db.scalar(select(Schedule).where(Schedule.id == run.schedule_id)) if run.schedule_id else None

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
        append_log(db, run_id, "INFO", f"Runtime environment: {run.env_name}")

        plan = _resolve_execution_plan(version=version, run_dir=run_dir, runtime_arguments=runtime_arguments)
        robot_env_values = resolve_runtime_env(db=db, robot_id=run.robot_id, env_name=run.env_name)
        merged_runtime_env = {**robot_env_values, **runtime_env}
        env = make_environment(version=version, runtime_env=merged_runtime_env)
        timeout_seconds = schedule.timeout_seconds if schedule else 3600

        append_log(db, run_id, "INFO", f"Command: {' '.join(plan.command)}")
        append_log(db, run_id, "INFO", f"Working directory: {plan.working_directory}")
        append_log(db, run_id, "INFO", f"Timeout seconds: {timeout_seconds}")

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
        started_monotonic = time.monotonic()
        timed_out = False
        canceled = False
        last_cancel_check = 0.0

        with log_file_path.open("a", encoding="utf-8") as log_file:
            while True:
                try:
                    item = line_queue.get(timeout=0.2)
                    append_log(db, run_id, item.level, item.message)
                    log_file.write(f"{utcnow().isoformat()} [{item.level}] {item.message}\n")
                    log_file.flush()
                except queue.Empty:
                    pass

                now_monotonic = time.monotonic()
                if process.poll() is None and (now_monotonic - last_cancel_check) >= 1:
                    last_cancel_check = now_monotonic
                    if _is_cancel_requested(db=db, run=run):
                        canceled = True
                        append_log(db, run_id, "INFO", "Execution canceled by user")
                        _terminate_process_tree(process)

                if (
                    not canceled
                    and process.poll() is None
                    and timeout_seconds > 0
                    and (now_monotonic - started_monotonic) > timeout_seconds
                ):
                    timed_out = True
                    _terminate_process_tree(process)
                    append_log(db, run_id, "ERROR", f"TIMEOUT: exceeded {timeout_seconds} seconds.")

                if process.poll() is not None and line_queue.empty() and not stdout_thread.is_alive() and not stderr_thread.is_alive():
                    break

        return_code = process.wait()
        finished_at = utcnow()
        run.finished_at = finished_at
        run.duration_seconds = (finished_at - (run.started_at or finished_at)).total_seconds()
        run.process_id = None

        if canceled:
            run.status = RunStatus.CANCELED.value
            run.error_message = None
            run.canceled_at = finished_at
            append_log(db, run_id, "INFO", "Execution marked as CANCELED.")
        elif return_code == 0 and not timed_out:
            run.status = RunStatus.SUCCESS.value
            run.error_message = None
            append_log(db, run_id, "INFO", "Execution finished successfully.")
        else:
            run.status = RunStatus.FAILED.value
            run.error_message = "TIMEOUT" if timed_out else f"Process returned exit code {return_code}"
            append_log(db, run_id, "ERROR", run.error_message)

        db.commit()
        register_artifacts(db=db, run=run, run_dir=run_dir)
        _schedule_retry_if_needed(
            db=db,
            run=run,
            schedule=schedule,
            runtime_arguments=runtime_arguments,
            runtime_env=runtime_env,
        )
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
    logger.info("Worker started, listening queue=%s worker_id=%s", queue_name, worker_id)

    _mark_worker_running()
    current_status = WorkerStatus.RUNNING.value
    last_heartbeat_ts = 0.0
    last_status_poll_ts = 0.0

    try:
        while True:
            now = time.time()
            if now - last_heartbeat_ts >= 10:
                last_heartbeat_ts = now
                worker_heartbeat.labels(worker=worker_name).set(now)
                current_status = _touch_worker_heartbeat()
                register_worker_heartbeat(worker_name=worker_name, ttl_seconds=max(60, settings.worker_stale_seconds * 2))

            if now - last_status_poll_ts >= 2:
                last_status_poll_ts = now
                current_status = _read_worker_status()

            refresh_queue_depth_sync()

            if current_status in {WorkerStatus.PAUSED.value, WorkerStatus.STOPPED.value}:
                time.sleep(2)
                continue

            item = redis.brpop(queue_name, timeout=5)
            if not item:
                continue

            _, raw_payload = item
            current_status = _read_worker_status()
            if current_status in {WorkerStatus.PAUSED.value, WorkerStatus.STOPPED.value}:
                redis.rpush(queue_name, raw_payload)
                time.sleep(1)
                continue

            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                logger.error("Invalid payload from queue: %s", raw_payload)
                continue

            not_before_ts = payload.get("not_before_ts")
            if isinstance(not_before_ts, (int, float)) and time.time() < float(not_before_ts):
                redis.rpush(queue_name, raw_payload)
                time.sleep(min(1.0, max(0.0, float(not_before_ts) - time.time())))
                continue

            process_run(payload)
    finally:
        _mark_worker_stopped()


def _schedule_retry_if_needed(
    db: Session,
    run: Run,
    schedule: Schedule | None,
    runtime_arguments: list[str],
    runtime_env: dict[str, str],
) -> None:
    if run.status != RunStatus.FAILED.value:
        return
    if not schedule:
        return
    if run.attempt > schedule.retry_count:
        return

    retry_attempt = run.attempt + 1
    retry_run = Run(
        robot_id=run.robot_id,
        robot_version_id=run.robot_version_id,
        service_id=run.service_id,
        schedule_id=run.schedule_id,
        env_name=run.env_name,
        trigger_type=TriggerType.RETRY.value,
        attempt=retry_attempt,
        parameters_json=run.parameters_json,
        status=RunStatus.PENDING.value,
        queued_at=utcnow(),
        triggered_by=run.triggered_by,
    )
    db.add(retry_run)
    db.commit()
    db.refresh(retry_run)

    retry_payload = {
        "run_id": str(retry_run.run_id),
        "robot_id": str(retry_run.robot_id),
        "robot_version_id": str(retry_run.robot_version_id),
        "runtime_arguments": runtime_arguments,
        "runtime_env": runtime_env,
        "triggered_by": str(retry_run.triggered_by) if retry_run.triggered_by else None,
        "service_id": str(retry_run.service_id) if retry_run.service_id else None,
        "schedule_id": str(retry_run.schedule_id) if retry_run.schedule_id else None,
        "trigger_type": TriggerType.RETRY.value,
        "attempt": retry_attempt,
        "parameters_json": retry_run.parameters_json or {},
        "env_name": retry_run.env_name,
        "not_before_ts": time.time() + max(1, schedule.retry_backoff_seconds),
    }
    redis = get_sync_redis()
    redis.lpush(settings.redis_queue_name, json.dumps(retry_payload))
    refresh_queue_depth_sync()
    append_log(
        db,
        run.run_id,
        "WARN",
        f"Retry scheduled: attempt={retry_attempt} backoff={schedule.retry_backoff_seconds}s run_id={retry_run.run_id}",
    )


if __name__ == "__main__":
    run_worker()
