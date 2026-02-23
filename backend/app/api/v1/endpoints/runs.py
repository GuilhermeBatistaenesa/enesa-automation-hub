from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import principal_has_scoped_grants, require_any_run_permission, require_permission, require_run_permission
from app.core.rbac import (
    PERMISSION_ARTIFACT_DOWNLOAD,
    PERMISSION_ROBOT_RUN,
    PERMISSION_RUN_CANCEL,
    PERMISSION_RUN_READ,
)
from app.db.session import get_db
from app.models.run import Run, RunStatus
from app.schemas.run import RunExecuteRequest, RunListResponse, RunLogRead, RunRead
from app.services.artifact_service import get_artifact, resolve_artifact_path
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.run_service import create_run_and_enqueue, get_run, get_run_logs, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/{robot_id}/execute", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED)
async def execute_robot(
    robot_id: UUID,
    payload: RunExecuteRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_RUN, robot_id_param="robot_id")),
) -> RunRead:
    try:
        run = await create_run_and_enqueue(
            db=db,
            robot_id=robot_id,
            payload=payload,
            triggered_by=principal.user.id if principal.user else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="run.triggered",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="run",
        target_id=str(run.run_id),
        metadata={"run_id": str(run.run_id), "robot_id": str(robot_id), "version_id": str(run.robot_version_id)},
    )
    return RunRead.model_validate(run)


@router.get("", response_model=RunListResponse)
def get_runs(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_RUN_READ, robot_id_param="robot_id")),
    robot_id: UUID | None = Query(None),
    service_id: UUID | None = Query(None),
    trigger_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> RunListResponse:
    if robot_id is None and principal_has_scoped_grants(db=db, principal=principal, permission=PERMISSION_RUN_READ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="robot_id is required for users with scoped run.read grants.",
        )
    items, total = list_runs(
        db=db,
        robot_id=robot_id,
        service_id=service_id,
        trigger_type=trigger_type,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return RunListResponse(items=[RunRead.model_validate(item) for item in items], total=total)


@router.get("/{run_id}", response_model=RunRead)
def get_run_by_id(
    run_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_run_permission(PERMISSION_RUN_READ)),
) -> RunRead:
    run = get_run(db=db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return RunRead.model_validate(run)


@router.post("/{run_id}/cancel", response_model=RunRead)
def cancel_run(
    run_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_any_run_permission([PERMISSION_ROBOT_RUN, PERMISSION_RUN_CANCEL])),
) -> RunRead:
    run = db.scalar(select(Run).where(Run.run_id == run_id))
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    if run.status == RunStatus.CANCELED.value:
        return RunRead.model_validate(get_run(db=db, run_id=run_id) or run)

    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only RUNNING runs can be canceled.")

    if not run.cancel_requested:
        run.cancel_requested = True
        run.canceled_by = principal.user.id if principal.user else None
        db.commit()
        db.refresh(run)

        log_audit_event(
            db=db,
            action="run_cancel_requested",
            principal=principal,
            actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
            target_type="run",
            target_id=str(run_id),
            metadata={
                "run_id": str(run_id),
                "robot_id": str(run.robot_id),
                "status": run.status,
                "cancel_requested": True,
            },
        )

    return RunRead.model_validate(get_run(db=db, run_id=run_id) or run)


@router.get("/{run_id}/logs", response_model=list[RunLogRead])
def get_logs(
    run_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_run_permission(PERMISSION_RUN_READ)),
    limit: int = Query(500, ge=1, le=5000),
) -> list[RunLogRead]:
    logs = get_run_logs(db=db, run_id=run_id, limit=limit)
    return [RunLogRead.model_validate(log) for log in logs]


@router.get("/{run_id}/artifacts/{artifact_id}/download")
def download_artifact(
    run_id: UUID,
    artifact_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_run_permission(PERMISSION_ARTIFACT_DOWNLOAD)),
) -> FileResponse:
    artifact = get_artifact(db=db, run_id=run_id, artifact_id=artifact_id)
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    run = db.scalar(select(Run).where(Run.run_id == run_id))
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    artifact_path = resolve_artifact_path(artifact)
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file not found on disk.")

    log_audit_event(
        db=db,
        action="artifact.downloaded",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={"run_id": str(run_id), "robot_id": str(run.robot_id), "artifact_id": str(artifact_id)},
    )
    return FileResponse(path=artifact_path, filename=artifact.artifact_name, media_type=artifact.content_type or "application/octet-stream")
