from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RunExecuteRequest(BaseModel):
    robot_version_id: UUID | None = None
    runtime_arguments: list[str] = Field(default_factory=list)
    runtime_env: dict[str, str] = Field(default_factory=dict)


class ArtifactRead(ORMModel):
    id: UUID
    run_id: UUID
    artifact_name: str
    file_path: str
    file_size_bytes: int
    content_type: str | None
    created_at: datetime


class RunLogRead(ORMModel):
    id: int
    run_id: UUID
    timestamp: datetime
    level: str
    message: str


class RunRead(ORMModel):
    run_id: UUID
    robot_id: UUID
    robot_version_id: UUID
    status: str
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    triggered_by: UUID | None
    error_message: str | None
    host_name: str | None
    process_id: int | None
    artifacts: list[ArtifactRead] = Field(default_factory=list)


class RunListResponse(ORMModel):
    items: list[RunRead]
    total: int


class WebSocketLogMessage(ORMModel):
    run_id: UUID
    timestamp: datetime
    level: str
    message: str

