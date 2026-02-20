from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.run import RunExecuteRequest, RunListResponse, RunLogRead, RunRead
from app.services.artifact_service import get_artifact, resolve_artifact_path
from app.services.run_service import create_run_and_enqueue, get_run, get_run_logs, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post(
    "/{robot_id}/execute",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permission("robots:execute", "robots"))],
)
async def execute_robot(
    robot_id: UUID,
    payload: RunExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("robots:execute", "robots")),
) -> RunRead:
    try:
        run = await create_run_and_enqueue(db=db, robot_id=robot_id, payload=payload, triggered_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RunRead.model_validate(run)


@router.get(
    "",
    response_model=RunListResponse,
    dependencies=[Depends(require_permission("runs:read", "runs"))],
)
def get_runs(
    db: Session = Depends(get_db),
    robot_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> RunListResponse:
    items, total = list_runs(db=db, robot_id=robot_id, status=status_filter, skip=skip, limit=limit)
    return RunListResponse(items=[RunRead.model_validate(item) for item in items], total=total)


@router.get(
    "/{run_id}",
    response_model=RunRead,
    dependencies=[Depends(require_permission("runs:read", "runs"))],
)
def get_run_by_id(run_id: UUID, db: Session = Depends(get_db)) -> RunRead:
    run = get_run(db=db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run não encontrado.")
    return RunRead.model_validate(run)


@router.get(
    "/{run_id}/logs",
    response_model=list[RunLogRead],
    dependencies=[Depends(require_permission("runs:logs:read", "runs"))],
)
def get_logs(run_id: UUID, db: Session = Depends(get_db), limit: int = Query(500, ge=1, le=5000)) -> list[RunLogRead]:
    logs = get_run_logs(db=db, run_id=run_id, limit=limit)
    return [RunLogRead.model_validate(log) for log in logs]


@router.get(
    "/{run_id}/artifacts/{artifact_id}/download",
    dependencies=[Depends(require_permission("artifacts:read", "artifacts"))],
)
def download_artifact(run_id: UUID, artifact_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    artifact = get_artifact(db=db, run_id=run_id, artifact_id=artifact_id)
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado.")

    artifact_path = resolve_artifact_path(artifact)
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de artefato não encontrado em disco.")

    return FileResponse(path=artifact_path, filename=artifact.artifact_name, media_type=artifact.content_type or "application/octet-stream")

