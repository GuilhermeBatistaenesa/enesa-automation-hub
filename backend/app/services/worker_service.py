from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.run import Run, RunStatus
from app.models.worker import Worker, WorkerStatus
from app.services.queue_service import get_queue_depth_sync


def list_workers(db: Session) -> list[Worker]:
    return list(db.scalars(select(Worker).order_by(Worker.hostname.asc(), Worker.created_at.asc())))


def get_worker(db: Session, worker_id: UUID) -> Worker | None:
    return db.scalar(select(Worker).where(Worker.id == worker_id))


def upsert_worker_heartbeat(
    db: Session,
    worker_id: UUID,
    hostname: str,
    version: str | None,
    status_if_new: str = WorkerStatus.RUNNING.value,
) -> Worker:
    worker = get_worker(db=db, worker_id=worker_id)
    now = datetime.now(timezone.utc)
    if not worker:
        worker = Worker(
            id=worker_id,
            hostname=hostname,
            status=status_if_new,
            last_heartbeat=now,
            version=version,
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        return worker

    worker.hostname = hostname
    worker.version = version
    worker.last_heartbeat = now
    db.commit()
    db.refresh(worker)
    return worker


def set_worker_status(db: Session, worker_id: UUID, status: str) -> Worker:
    worker = get_worker(db=db, worker_id=worker_id)
    if not worker:
        raise ValueError("Worker not found.")
    worker.status = status
    db.commit()
    db.refresh(worker)
    return worker


def get_ops_status(db: Session, started_at_monotonic: float) -> dict[str, int]:
    total_workers = db.scalar(select(func.count()).select_from(Worker)) or 0
    workers_running = db.scalar(
        select(func.count()).select_from(Worker).where(Worker.status == WorkerStatus.RUNNING.value)
    ) or 0
    workers_paused = db.scalar(
        select(func.count()).select_from(Worker).where(Worker.status == WorkerStatus.PAUSED.value)
    ) or 0

    runs_running = db.scalar(
        select(func.count()).select_from(Run).where(Run.status == RunStatus.RUNNING.value)
    ) or 0

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    runs_failed_last_hour = db.scalar(
        select(func.count())
        .select_from(Run)
        .where(
            Run.status == RunStatus.FAILED.value,
            func.coalesce(Run.finished_at, Run.queued_at) >= one_hour_ago,
        )
    ) or 0

    queue_depth = get_queue_depth_sync()
    uptime_seconds = int(max(0, time.monotonic() - started_at_monotonic))

    return {
        "total_workers": int(total_workers),
        "workers_running": int(workers_running),
        "workers_paused": int(workers_paused),
        "queue_depth": int(queue_depth),
        "runs_running": int(runs_running),
        "runs_failed_last_hour": int(runs_failed_last_hour),
        "uptime_seconds": uptime_seconds,
    }
