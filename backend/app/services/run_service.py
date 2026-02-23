from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.robot import RobotVersion
from app.models.run import Run, RunLog, RunStatus
from app.models.scheduler import TriggerType
from app.schemas.run import RunExecuteRequest
from app.services.robot_env_service import list_defined_env_keys, normalize_env_name
from app.services.queue_service import enqueue_run


def _resolve_robot_version(db: Session, robot_id: UUID, requested_version_id: UUID | None) -> RobotVersion:
    if requested_version_id:
        version = db.scalar(select(RobotVersion).where(RobotVersion.id == requested_version_id, RobotVersion.robot_id == robot_id))
    else:
        version = db.scalar(
            select(RobotVersion)
            .where(RobotVersion.robot_id == robot_id, RobotVersion.is_active.is_(True))
            .order_by(RobotVersion.created_at.desc())
        )
    if not version:
        raise ValueError("Robot version not found for execution.")
    return version


async def create_run_and_enqueue(
    db: Session,
    robot_id: UUID,
    payload: RunExecuteRequest,
    triggered_by: UUID | None,
    service_id: UUID | None = None,
    parameters_json: dict | None = None,
    trigger_type: str = TriggerType.MANUAL.value,
    attempt: int = 1,
    schedule_id: UUID | None = None,
    not_before_ts: float | None = None,
) -> Run:
    version = _resolve_robot_version(db, robot_id=robot_id, requested_version_id=payload.resolved_version_id)
    env_name = normalize_env_name(payload.env_name)
    _validate_required_env_keys(db=db, robot_id=robot_id, env_name=env_name, required_keys=version.required_env_keys_json or [])

    run = Run(
        robot_id=robot_id,
        robot_version_id=version.id,
        service_id=service_id,
        schedule_id=schedule_id,
        env_name=env_name,
        parameters_json=parameters_json,
        trigger_type=trigger_type,
        attempt=attempt,
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
            "service_id": str(service_id) if service_id else None,
            "schedule_id": str(schedule_id) if schedule_id else None,
            "trigger_type": trigger_type,
            "attempt": attempt,
            "parameters_json": parameters_json or {},
            "env_name": env_name,
            "not_before_ts": not_before_ts,
        }
    )

    return get_run(db=db, run_id=run.run_id) or run


def list_runs(
    db: Session,
    robot_id: UUID | None = None,
    service_id: UUID | None = None,
    trigger_type: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Run], int]:
    base_stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)

    if robot_id:
        base_stmt = base_stmt.where(Run.robot_id == robot_id)
        count_stmt = count_stmt.where(Run.robot_id == robot_id)

    if service_id:
        base_stmt = base_stmt.where(Run.service_id == service_id)
        count_stmt = count_stmt.where(Run.service_id == service_id)

    if trigger_type:
        base_stmt = base_stmt.where(Run.trigger_type == trigger_type)
        count_stmt = count_stmt.where(Run.trigger_type == trigger_type)

    if status:
        base_stmt = base_stmt.where(Run.status == status)
        count_stmt = count_stmt.where(Run.status == status)

    total = db.scalar(count_stmt) or 0

    items = list(
        db.scalars(
            base_stmt.options(selectinload(Run.artifacts), joinedload(Run.robot_version), joinedload(Run.service), joinedload(Run.schedule))
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
        .options(
            selectinload(Run.artifacts),
            joinedload(Run.robot),
            joinedload(Run.robot_version),
            joinedload(Run.service),
            joinedload(Run.schedule),
        )
    )
    return db.scalar(stmt)


def get_run_logs(db: Session, run_id: UUID, limit: int = 500) -> list[RunLog]:
    return list(db.scalars(select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.id.asc()).limit(limit)))


def _validate_required_env_keys(db: Session, robot_id: UUID, env_name: str, required_keys: list[str]) -> None:
    normalized_required = sorted({item.strip() for item in required_keys if isinstance(item, str) and item.strip()})
    if not normalized_required:
        return

    defined_keys = list_defined_env_keys(db=db, robot_id=robot_id, env_name=env_name)
    missing = [item for item in normalized_required if item not in defined_keys]
    if missing:
        raise ValueError(
            f"Missing required env vars for {env_name}: {', '.join(missing)}. "
            "Configure keys in Robot > Config/Secrets before executing."
        )
