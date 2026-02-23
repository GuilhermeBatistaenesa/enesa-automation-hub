from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.rbac import PERMISSION_WORKER_MANAGE
from app.db.session import get_db
from app.models.worker import WorkerStatus
from app.schemas.worker import WorkerRead
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.worker_service import list_workers, set_worker_status

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerRead])
def get_workers(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_WORKER_MANAGE)),
) -> list[WorkerRead]:
    return [WorkerRead.model_validate(item) for item in list_workers(db=db)]


@router.post("/{worker_id}/pause", response_model=WorkerRead)
def pause_worker(
    worker_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_WORKER_MANAGE)),
) -> WorkerRead:
    try:
        worker = set_worker_status(db=db, worker_id=worker_id, status=WorkerStatus.PAUSED.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="worker.paused",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="worker",
        target_id=str(worker.id),
        metadata={"worker_id": str(worker.id), "hostname": worker.hostname, "status": worker.status},
    )
    return WorkerRead.model_validate(worker)


@router.post("/{worker_id}/resume", response_model=WorkerRead)
def resume_worker(
    worker_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_WORKER_MANAGE)),
) -> WorkerRead:
    try:
        worker = set_worker_status(db=db, worker_id=worker_id, status=WorkerStatus.RUNNING.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="worker.resumed",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="worker",
        target_id=str(worker.id),
        metadata={"worker_id": str(worker.id), "hostname": worker.hostname, "status": worker.status},
    )
    return WorkerRead.model_validate(worker)
