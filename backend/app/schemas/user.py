from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMModel


class UserRead(ORMModel):
    id: UUID
    username: str
    full_name: str | None
    email: str | None
    is_active: bool
    is_superuser: bool
    auth_source: str
    created_at: datetime

