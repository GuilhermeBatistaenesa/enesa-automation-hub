from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import engine
from app.models.permission import Permission
from app.models.user import User


DEFAULT_PERMISSIONS = [
    ("robots", "robots:create"),
    ("robots", "robots:read"),
    ("robots", "robots:execute"),
    ("runs", "runs:read"),
    ("runs", "runs:logs:read"),
    ("artifacts", "artifacts:read"),
]


def bootstrap_database(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    _seed_admin_user(db)


def _seed_admin_user(db: Session) -> None:
    settings = get_settings()
    existing = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if existing:
        return

    admin = User(
        username=settings.default_admin_username,
        email=settings.default_admin_email,
        full_name="Administrador Enesa Automation Hub",
        hashed_password=get_password_hash(settings.default_admin_password),
        is_active=True,
        is_superuser=True,
        auth_source="local",
    )
    db.add(admin)
    db.flush()

    for resource_type, action in DEFAULT_PERMISSIONS:
        db.add(
            Permission(
                user_id=admin.id,
                resource_type=resource_type,
                action=action,
            )
        )

    db.commit()

