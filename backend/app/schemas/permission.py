from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PermissionRead(ORMModel):
    id: int
    user_id: UUID
    resource_type: str
    resource_id: UUID | None
    scope_tag: str | None
    action: str
    created_at: datetime


class PermissionGrantRequest(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=80)
    resource_id: UUID | None = None
    scope_tag: str | None = Field(default=None, max_length=100)
