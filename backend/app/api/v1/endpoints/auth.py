from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_principal
from app.core.config import get_settings
from app.core.rbac import Role
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthUser, Token
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    if not settings.allow_local_auth:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local authentication is disabled.")

    user = db.scalar(select(User).where(or_(User.username == form_data.username, User.email == form_data.username)))
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid username or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user.")

    token = create_access_token(str(user.id), extra={"auth_source": "local"})
    local_principal = Principal(
        subject=str(user.id),
        auth_source="local",
        role=(Role.ADMIN if user.is_superuser else Role.VIEWER),
        permissions=set(),
        user=user,
    )
    log_audit_event(
        db=db,
        action="auth.local_login",
        principal=local_principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="user",
        target_id=str(user.id),
        metadata={"username": user.username},
    )
    return Token(access_token=token)


@router.get("/me", response_model=AuthUser)
def get_me(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> AuthUser:
    log_audit_event(
        db=db,
        action=("auth.azure_login" if principal.auth_source == "azure_ad" else "auth.local_token_used"),
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="user",
        target_id=(str(principal.user.id) if principal.user else principal.subject),
        metadata={
            "username": principal.user.username if principal.user else None,
            "subject": principal.subject,
            "auth_source": principal.auth_source,
        },
    )
    return AuthUser(user=principal.user, subject=principal.subject, role=principal.role.value, auth_source=principal.auth_source)
