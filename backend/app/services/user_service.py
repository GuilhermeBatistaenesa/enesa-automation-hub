from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import ALL_PERMISSIONS, PERMISSION_RESOURCE_TYPES
from app.core.security import get_password_hash
from app.models.permission import Permission
from app.models.user import User
from app.schemas.permission import PermissionGrantRequest
from app.schemas.user import UserCreate


def create_user(db: Session, payload: UserCreate) -> User:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise ValueError("Username already exists.")

    user = User(
        username=payload.username,
        email=str(payload.email) if payload.email else None,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_superuser=payload.is_superuser,
        is_active=True,
        auth_source="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)))


def grant_permission(db: Session, user_id: UUID, payload: PermissionGrantRequest) -> Permission:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise ValueError("User not found.")

    if payload.action not in ALL_PERMISSIONS:
        raise ValueError("Invalid permission action.")
    expected_resource_type = PERMISSION_RESOURCE_TYPES[payload.action]
    if payload.resource_type != expected_resource_type:
        raise ValueError(f"resource_type must be '{expected_resource_type}' for action '{payload.action}'.")

    permission = Permission(
        user_id=user_id,
        resource_type=payload.resource_type,
        action=payload.action,
        resource_id=payload.resource_id,
        scope_tag=payload.scope_tag,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def list_permissions(db: Session, user_id: UUID) -> list[Permission]:
    return list(
        db.scalars(
            select(Permission).where(Permission.user_id == user_id).order_by(Permission.resource_type.asc(), Permission.action.asc())
        )
    )
