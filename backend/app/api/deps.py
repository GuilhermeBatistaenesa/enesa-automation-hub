from __future__ import annotations

from collections.abc import Callable
import hmac
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.permission import Permission
from app.models.robot import RobotTag
from app.models.run import Run
from app.services.identity_service import Principal, authenticate_token

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token")


def get_current_principal(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Principal:
    return authenticate_token(db=db, token=token)


def require_deploy_token(request: Request) -> str:
    header_token = request.headers.get("x-deploy-token")
    auth = request.headers.get("authorization")
    bearer_token = None
    if auth and auth.lower().startswith("bearer "):
        bearer_token = auth.split(" ", 1)[1].strip()
    provided = (header_token or bearer_token or "").strip()
    expected = settings.deploy_token.strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DEPLOY_TOKEN is not configured.")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid deploy token.")
    return "github_actions"


def authenticate_websocket_principal(token: str, db: Session) -> Principal:
    return authenticate_token(db=db, token=token)


def _robot_tag_set(db: Session, robot_id: UUID) -> set[str]:
    return set(db.scalars(select(RobotTag.tag).where(RobotTag.robot_id == robot_id)))


def _principal_explicit_grants(db: Session, principal: Principal, permission: str) -> list[Permission]:
    if not principal.user:
        return []
    return list(
        db.scalars(
            select(Permission).where(
                and_(
                    Permission.user_id == principal.user.id,
                    Permission.action == permission,
                )
            )
        )
    )


def _has_permission_for_robot(db: Session, principal: Principal, permission: str, robot_id: UUID | None) -> bool:
    if principal.is_admin:
        return True

    if permission not in principal.permissions:
        return False

    if robot_id is None:
        return True

    grants = _principal_explicit_grants(db=db, principal=principal, permission=permission)
    if not grants:
        return True

    tags = _robot_tag_set(db=db, robot_id=robot_id)
    for grant in grants:
        if grant.resource_id is None and not grant.scope_tag:
            return True
        if grant.resource_id and grant.resource_id == robot_id:
            return True
        if grant.scope_tag and grant.scope_tag in tags:
            return True
    return False


def require_permission(permission: str, robot_id_param: str | None = None) -> Callable:
    def dependency(
        request: Request,
        principal: Principal = Depends(get_current_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        robot_id: UUID | None = None
        if robot_id_param:
            raw = request.path_params.get(robot_id_param) or request.query_params.get(robot_id_param)
            if raw:
                try:
                    robot_id = UUID(str(raw))
                except ValueError as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="robot_id invalido.") from exc

        if not _has_permission_for_robot(db=db, principal=principal, permission=permission, robot_id=robot_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")
        return principal

    return dependency


def require_run_permission(permission: str, run_id_param: str = "run_id") -> Callable:
    def dependency(
        request: Request,
        principal: Principal = Depends(get_current_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        raw_run_id = request.path_params.get(run_id_param)
        if not raw_run_id:
            if permission in principal.permissions or principal.is_admin:
                return principal
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")

        try:
            run_id = UUID(str(raw_run_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id invalido.") from exc

        run = db.scalar(select(Run).where(Run.run_id == run_id))
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run nao encontrada.")

        if not _has_permission_for_robot(db=db, principal=principal, permission=permission, robot_id=run.robot_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")
        return principal

    return dependency


def require_any_run_permission(permissions: list[str], run_id_param: str = "run_id") -> Callable:
    def dependency(
        request: Request,
        principal: Principal = Depends(get_current_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        raw_run_id = request.path_params.get(run_id_param)
        if not raw_run_id:
            if principal.is_admin or any(permission in principal.permissions for permission in permissions):
                return principal
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")

        try:
            run_id = UUID(str(raw_run_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id invalido.") from exc

        run = db.scalar(select(Run).where(Run.run_id == run_id))
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run nao encontrada.")

        for permission in permissions:
            if _has_permission_for_robot(db=db, principal=principal, permission=permission, robot_id=run.robot_id):
                return principal

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")

    return dependency


def can_access_run(db: Session, principal: Principal, run_id: UUID, permission: str) -> bool:
    run = db.scalar(select(Run).where(Run.run_id == run_id))
    if not run:
        return False
    return _has_permission_for_robot(db=db, principal=principal, permission=permission, robot_id=run.robot_id)


def principal_has_scoped_grants(db: Session, principal: Principal, permission: str) -> bool:
    grants = _principal_explicit_grants(db=db, principal=principal, permission=permission)
    if not grants:
        return False
    for grant in grants:
        if grant.resource_id is not None or grant.scope_tag:
            return True
    return False


def allowed_robot_ids_for_permission(db: Session, principal: Principal, permission: str) -> set[UUID] | None:
    if principal.is_admin:
        return None

    grants = _principal_explicit_grants(db=db, principal=principal, permission=permission)
    if not grants:
        return None

    for grant in grants:
        if grant.resource_id is None and not grant.scope_tag:
            return None

    allowed_ids: set[UUID] = set()
    scope_tags: set[str] = set()
    for grant in grants:
        if grant.resource_id:
            allowed_ids.add(grant.resource_id)
        if grant.scope_tag:
            scope_tags.add(grant.scope_tag)

    if scope_tags:
        tagged_robot_ids = db.scalars(select(RobotTag.robot_id).where(RobotTag.tag.in_(scope_tags)))
        allowed_ids.update(tagged_robot_ids)

    return allowed_ids
