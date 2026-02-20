from __future__ import annotations

from app.schemas.common import ORMModel
from app.schemas.user import UserRead


class Token(ORMModel):
    access_token: str
    token_type: str = "bearer"


class AuthUser(ORMModel):
    user: UserRead

