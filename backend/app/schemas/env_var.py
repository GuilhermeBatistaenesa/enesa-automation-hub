from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RobotEnvVarUpsertItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=150, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str | None = Field(default=None, max_length=10000)
    is_secret: bool = False


class RobotEnvVarUpsertRequest(BaseModel):
    items: list[RobotEnvVarUpsertItem] = Field(default_factory=list)


class RobotEnvVarRead(ORMModel):
    robot_id: UUID
    env_name: str
    key: str
    is_secret: bool
    is_set: bool
    value: str | None = None
    created_at: datetime
    updated_at: datetime
