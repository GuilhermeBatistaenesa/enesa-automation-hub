from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RobotVersionBase(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    entrypoint_type: str = Field(..., pattern="^(PYTHON|EXE)$")
    entrypoint_path: str = Field(..., min_length=1, max_length=1024)
    arguments: list[str] = Field(default_factory=list)
    env_vars: dict[str, str] = Field(default_factory=dict)
    working_directory: str | None = Field(default=None, max_length=1024)
    checksum: str | None = Field(default=None, max_length=255)


class RobotCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = None
    initial_version: RobotVersionBase


class RobotVersionRead(ORMModel):
    id: UUID
    robot_id: UUID
    version: str
    entrypoint_type: str
    entrypoint_path: str
    arguments: list[str]
    env_vars: dict[str, str]
    working_directory: str | None
    checksum: str | None
    created_at: datetime
    is_active: bool


class RobotRead(ORMModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    versions: list[RobotVersionRead]


class RobotListResponse(ORMModel):
    items: list[RobotRead]
    total: int

