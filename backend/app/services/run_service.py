from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.robot import RobotVersion
from app.models.run import Run, RunLog, RunStatus
from app.schemas.run import RunExecuteRequest
from app.services.queue_service import enqueue_run


def _resolve_robot_version(db: Session, robot_id: UUID, requested_version_id: UUID | None) -> RobotVersion:
    if requested_version_id:
        version = db.scalar(
            select(RobotVersion).where(RobotVersion.id == requested_version_id, RobotVersion.robot_id == robot_id)
        )
    else:
        version = db.scalar(
            select(RobotVersion)
            .where(RobotVersion.robot_id == robot_id, RobotVersion.is_active.is_(True))
            .order_by(desc(RobotVersion.created_at))
        )
    if not version:
        raise ValueError("Versão de robô não encontrada para execução.")
    return version


async def create_run_and_enqueue(
    db: Session,
    robot_id: UUID,
    payload: RunExecuteRequest,
    triggered_by: UUID | None,
) -> Run:
    version = _resolve_robot_version(db, robot_id=robot_id, requested_version_id=payload.robot_version_id)

    run = Run(
        robot_id=robot_id,
        robot_version_id=version.id,
        status=RunStatus.PENDING.value,
        queued_at=datetime.now(timezone.utc),
        triggered_by=triggered_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    await enqueue_run(
        {
            "run_id": str(run.run_id),
            "robot_id": str(robot_id),
            "robot_version_id": str(version.id),
            "runtime_arguments": payload.runtime_arguments,
            "runtime_env": payload.runtime_env,
            "triggered_by": str(triggered_by) if triggered_by else None,
        }
    )
    return run


def list_runs(
    db: Session,
    robot_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Run], int]:
    base_stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)

    if robot_id:
        base_stmt = base_stmt.where(Run.robot_id == robot_id)
        count_stmt = count_stmt.where(Run.robot_id == robot_id)

    if status:
        base_stmt = base_stmt.where(Run.status == status)
        count_stmt = count_stmt.where(Run.status == status)

    total = db.scalar(count_stmt) or 0

    items = list(
        db.scalars(
            base_stmt.options(selectinload(Run.artifacts))
            .order_by(Run.queued_at.desc())
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def get_run(db: Session, run_id: UUID) -> Run | None:
    stmt = (
        select(Run)
        .where(Run.run_id == run_id)
        .options(selectinload(Run.artifacts), joinedload(Run.robot), joinedload(Run.robot_version))
    )
    return db.scalar(stmt)


def get_run_logs(db: Session, run_id: UUID, limit: int = 500) -> list[RunLog]:
    return list(db.scalars(select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.id.asc()).limit(limit)))

