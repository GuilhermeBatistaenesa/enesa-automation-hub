from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

SEMVER_REGEX = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"


class RobotVersionBase(BaseModel):
    version: str = Field(..., pattern=SEMVER_REGEX, max_length=50)
    entrypoint_type: str = Field(default="PYTHON", pattern="^(PYTHON|EXE)$")
    entrypoint_path: str = Field(default="main.py", min_length=1, max_length=1024)
    arguments: list[str] = Field(default_factory=list)
    env_vars: dict[str, str] = Field(default_factory=dict)
    working_directory: str | None = Field(default=None, max_length=1024)
    checksum: str | None = Field(default=None, max_length=255)
    channel: str = Field(default="stable", pattern="^(stable|beta|hotfix)$")
    artifact_type: str = Field(default="ZIP", pattern="^(ZIP|EXE)$")
    artifact_path: str | None = Field(default=None, max_length=2048)
    artifact_sha256: str | None = Field(default=None, max_length=128)
    changelog: str | None = None


class RobotCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    initial_version: RobotVersionBase


class RobotVersionCreate(RobotVersionBase):
    is_active: bool = True


class RobotVersionPublishResult(ORMModel):
    id: UUID
    robot_id: UUID
    version: str
    channel: str
    artifact_type: str
    artifact_path: str | None
    artifact_sha256: str | None
    changelog: str | None
    commit_sha: str | None
    branch: str | None
    build_url: str | None
    created_source: str
    required_env_keys_json: list[str] = Field(default_factory=list)
    entrypoint_type: str
    entrypoint_path: str
    arguments: list[str]
    env_vars: dict[str, str]
    working_directory: str | None
    created_by: UUID | None
    created_at: datetime
    is_active: bool


class RobotTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)


class RobotVersionRead(ORMModel):
    id: UUID
    robot_id: UUID
    version: str
    channel: str
    artifact_type: str
    artifact_path: str | None
    artifact_sha256: str | None
    changelog: str | None
    commit_sha: str | None
    branch: str | None
    build_url: str | None
    created_source: str
    required_env_keys_json: list[str] = Field(default_factory=list)
    entrypoint_type: str
    entrypoint_path: str
    arguments: list[str]
    env_vars: dict[str, str]
    working_directory: str | None
    checksum: str | None
    created_by: UUID | None
    created_at: datetime
    is_active: bool


class RobotRead(ORMModel):
    id: UUID
    name: str
    description: str | None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    versions: list[RobotVersionRead]


class RobotListResponse(ORMModel):
    items: list[RobotRead]
    total: int
