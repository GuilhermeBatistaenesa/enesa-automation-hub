from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.core.rbac import (
    PERMISSION_ADMIN_MANAGE,
    PERMISSION_ARTIFACT_DOWNLOAD,
    PERMISSION_ROBOT_PUBLISH,
    PERMISSION_ROBOT_READ,
    PERMISSION_ROBOT_RUN,
    PERMISSION_RUN_READ,
    PERMISSION_SERVICE_MANAGE,
    PERMISSION_SERVICE_READ,
    PERMISSION_SERVICE_RUN,
)
from app.db.base import Base
from app.db.session import engine
from app.models.permission import Permission
from app.models.user import User


DEFAULT_PERMISSIONS = [
    ("robot", PERMISSION_ROBOT_PUBLISH),
    ("robot", PERMISSION_ROBOT_READ),
    ("robot", PERMISSION_ROBOT_RUN),
    ("run", PERMISSION_RUN_READ),
    ("artifact", PERMISSION_ARTIFACT_DOWNLOAD),
    ("service", PERMISSION_SERVICE_READ),
    ("service", PERMISSION_SERVICE_RUN),
    ("service", PERMISSION_SERVICE_MANAGE),
    ("admin", PERMISSION_ADMIN_MANAGE),
]


def bootstrap_database(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    _seed_admin_user(db)


def _seed_admin_user(db: Session) -> None:
    settings = get_settings()
    existing = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if not existing:
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
    else:
        admin = existing

    existing_pairs = set(
        db.execute(select(Permission.resource_type, Permission.action).where(Permission.user_id == admin.id)).all()
    )
    for resource_type, action in DEFAULT_PERMISSIONS:
        if (resource_type, action) in existing_pairs:
            continue
        db.add(
            Permission(
                user_id=admin.id,
                resource_type=resource_type,
                action=action,
            )
        )

    db.commit()
