from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rbac import (
    ALL_PERMISSIONS,
    PERMISSION_ADMIN_MANAGE,
    PERMISSION_ROBOT_PUBLISH,
    PERMISSION_ROBOT_RUN,
    PERMISSION_SERVICE_MANAGE,
    PERMISSION_SERVICE_RUN,
    Role,
    permissions_for_role,
)
from app.core.security import get_password_hash
from app.models.permission import Permission
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Principal:
    subject: str
    auth_source: str
    role: Role
    permissions: set[str]
    user: User | None = None
    groups: set[str] | None = None
    claims: dict[str, Any] | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN or PERMISSION_ADMIN_MANAGE in self.permissions


class AzureTokenValidator:
    def __init__(self) -> None:
        self._jwks_client = PyJWKClient(settings.resolved_azure_jwks_url) if settings.resolved_azure_jwks_url else None

    def validate(self, token: str) -> dict[str, Any]:
        if not settings.azure_enabled:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Azure AD is not enabled.")
        if not self._jwks_client:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Azure JWKS URL is not configured.")

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.azure_ad_audience,
                issuer=settings.resolved_azure_issuer,
                options={"verify_signature": True, "verify_exp": True, "verify_aud": True, "verify_iss": True},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Azure token validation failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Azure AD token.") from exc


azure_token_validator = AzureTokenValidator()


def _role_from_groups(groups: set[str]) -> Role:
    if groups & settings.azure_group_admin_list:
        return Role.ADMIN
    if groups & settings.azure_group_operator_list and groups & settings.azure_group_viewer_list:
        return Role.OPERATOR
    if groups & settings.azure_group_operator_list:
        return Role.OPERATOR
    if groups & settings.azure_group_viewer_list:
        return Role.VIEWER
    return Role.VIEWER


def _permissions_from_user_entries(db: Session, user_id: uuid.UUID) -> set[str]:
    actions = db.scalars(select(Permission.action).where(Permission.user_id == user_id))
    return {action for action in actions if action in ALL_PERMISSIONS}


def _build_local_principal(db: Session, token: str) -> Principal | None:
    from jose import jwt as jose_jwt

    try:
        payload = jose_jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        if not subject:
            return None
        user_id = uuid.UUID(subject)
    except Exception:  # noqa: BLE001
        return None

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local user token.")

    user_permissions = _permissions_from_user_entries(db=db, user_id=user.id)
    role = (
        Role.ADMIN
        if user.is_superuser or PERMISSION_ADMIN_MANAGE in user_permissions or PERMISSION_SERVICE_MANAGE in user_permissions
        else Role.VIEWER
    )
    if role == Role.VIEWER and PERMISSION_ROBOT_PUBLISH in user_permissions:
        role = Role.MAINTAINER
    elif role == Role.VIEWER and (PERMISSION_ROBOT_RUN in user_permissions or PERMISSION_SERVICE_RUN in user_permissions):
        role = Role.OPERATOR

    effective_permissions = permissions_for_role(role) | user_permissions
    return Principal(
        subject=str(user.id),
        auth_source="local",
        role=role,
        permissions=effective_permissions,
        user=user,
        groups=set(),
        claims=payload,
    )


def _resolve_or_create_azure_user(db: Session, payload: dict[str, Any]) -> User | None:
    oid = payload.get("oid") or payload.get("sub")
    if not oid:
        return None

    existing = db.scalar(select(User).where(User.azure_object_id == oid))
    if existing:
        if not existing.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Azure AD user is inactive in Enesa Hub.")
        return existing

    if not settings.auto_provision_azure_users:
        return None

    preferred_username = (payload.get("preferred_username") or payload.get("upn") or f"azure-{oid}")[:128]
    email = payload.get("email") or payload.get("preferred_username")
    full_name = payload.get("name") or preferred_username

    user = User(
        username=preferred_username,
        full_name=str(full_name)[:255],
        email=(str(email)[:255] if email else None),
        hashed_password=get_password_hash(secrets.token_urlsafe(24)),
        is_active=True,
        is_superuser=False,
        auth_source="azure_ad",
        azure_object_id=str(oid),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_azure_principal(db: Session, token: str) -> Principal | None:
    if settings.auth_mode not in {"hybrid", "azure"}:
        return None

    payload = azure_token_validator.validate(token)
    groups = set(payload.get("groups", []))
    role = _role_from_groups(groups)

    user = _resolve_or_create_azure_user(db=db, payload=payload)
    user_permissions = _permissions_from_user_entries(db, user.id) if user else set()
    if role == Role.VIEWER and PERMISSION_ROBOT_PUBLISH in user_permissions:
        role = Role.MAINTAINER
    elif role == Role.VIEWER and (PERMISSION_ROBOT_RUN in user_permissions or PERMISSION_SERVICE_RUN in user_permissions):
        role = Role.OPERATOR
    effective_permissions = permissions_for_role(role) | user_permissions

    subject = str(payload.get("oid") or payload.get("sub"))
    return Principal(
        subject=subject,
        auth_source="azure_ad",
        role=role,
        permissions=effective_permissions,
        user=user,
        groups=groups,
        claims=payload,
    )


def authenticate_token(db: Session, token: str) -> Principal:
    local_first = settings.auth_mode in {"hybrid", "local"}
    azure_enabled = settings.auth_mode in {"hybrid", "azure"} and settings.azure_enabled

    if local_first and settings.allow_local_auth:
        local_principal = _build_local_principal(db=db, token=token)
        if local_principal:
            return local_principal

    if azure_enabled:
        azure_principal = _build_azure_principal(db=db, token=token)
        if azure_principal:
            return azure_principal

    if local_first and not settings.allow_local_auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Local authentication is disabled.")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or unsupported.")
