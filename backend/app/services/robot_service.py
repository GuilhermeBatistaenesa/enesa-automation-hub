from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.robot import Robot, RobotVersion
from app.schemas.robot import RobotCreate


def create_robot(db: Session, payload: RobotCreate, created_by: object | None) -> Robot:
    robot = Robot(
        name=payload.name,
        description=payload.description,
        created_by=created_by,
    )
    db.add(robot)
    db.flush()

    version = RobotVersion(
        robot_id=robot.id,
        version=payload.initial_version.version,
        entrypoint_type=payload.initial_version.entrypoint_type,
        entrypoint_path=payload.initial_version.entrypoint_path,
        arguments=payload.initial_version.arguments,
        env_vars=payload.initial_version.env_vars,
        working_directory=payload.initial_version.working_directory,
        checksum=payload.initial_version.checksum,
        created_by=created_by,
        is_active=True,
    )
    db.add(version)
    db.commit()

    query = select(Robot).where(Robot.id == robot.id).options(selectinload(Robot.versions))
    return db.scalar(query)


def list_robots(db: Session, skip: int = 0, limit: int = 50) -> tuple[list[Robot], int]:
    total = db.scalar(select(func.count()).select_from(Robot)) or 0
    robots = list(
        db.scalars(
            select(Robot)
            .order_by(Robot.created_at.desc())
            .options(selectinload(Robot.versions))
            .offset(skip)
            .limit(limit)
        )
    )
    return robots, total

