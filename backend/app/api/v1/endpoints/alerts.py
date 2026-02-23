from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.rbac import PERMISSION_ADMIN_MANAGE, PERMISSION_RUN_READ
from app.db.session import get_db
from app.schemas.scheduler import AlertEventRead
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.scheduler_service import list_alerts, resolve_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertEventRead])
def get_alerts(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_RUN_READ)),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|resolved)?$"),
    alert_type: str | None = Query(default=None, alias="type"),
    robot_id: UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AlertEventRead]:
    items = list_alerts(db=db, status=status_filter, alert_type=alert_type, robot_id=robot_id, limit=limit)
    return [AlertEventRead.model_validate(item) for item in items]


@router.post("/{alert_id}/resolve", response_model=AlertEventRead)
def resolve_alert_endpoint(
    alert_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ADMIN_MANAGE)),
) -> AlertEventRead:
    try:
        alert = resolve_alert(db=db, alert_id=alert_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="alert.resolved",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="alert",
        target_id=str(alert_id),
        metadata={"alert_id": str(alert_id), "robot_id": str(alert.robot_id), "type": alert.type},
    )
    return AlertEventRead.model_validate(alert)
