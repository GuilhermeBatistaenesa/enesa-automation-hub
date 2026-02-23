from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMModel


class WorkerRead(ORMModel):
    id: UUID
    hostname: str
    status: str
    last_heartbeat: datetime
    version: str | None
    created_at: datetime


class OpsStatusRead(ORMModel):
    total_workers: int
    workers_running: int
    workers_paused: int
    queue_depth: int
    runs_running: int
    runs_failed_last_hour: int
    uptime_seconds: int
