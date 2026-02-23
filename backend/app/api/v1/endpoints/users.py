from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.rbac import PERMISSION_ADMIN_MANAGE
from app.db.session import get_db
from app.schemas.permission import PermissionGrantRequest, PermissionRead
from app.schemas.user import UserCreate, UserRead
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.user_service import create_user, grant_permission, list_permissions, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ADMIN_MANAGE)),
) -> UserRead:
    try:
        created = create_user(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="user.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="user",
        target_id=str(created.id),
        metadata={"user_id": str(created.id), "username": created.username},
    )
    return UserRead.model_validate(created)


@router.get("", response_model=list[UserRead])
def get_users(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ADMIN_MANAGE)),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[UserRead]:
    users = list_users(db=db, skip=skip, limit=limit)
    return [UserRead.model_validate(user) for user in users]


@router.get("/{user_id}/permissions", response_model=list[PermissionRead])
def get_user_permissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ADMIN_MANAGE)),
) -> list[PermissionRead]:
    permissions = list_permissions(db=db, user_id=user_id)
    return [PermissionRead.model_validate(item) for item in permissions]


@router.post("/{user_id}/permissions", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
def assign_permission(
    user_id: UUID,
    payload: PermissionGrantRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ADMIN_MANAGE)),
) -> PermissionRead:
    try:
        permission = grant_permission(db=db, user_id=user_id, payload=payload)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="permission.granted",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="permission",
        target_id=str(permission.id),
        metadata={
            "target_user_id": str(user_id),
            "action": payload.action,
            "resource_type": payload.resource_type,
            "resource_id": str(payload.resource_id) if payload.resource_id else None,
            "scope_tag": payload.scope_tag,
        },
    )
    return PermissionRead.model_validate(permission)
