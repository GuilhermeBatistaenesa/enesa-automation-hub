from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.robot import Robot, RobotReleaseTag, RobotTag, RobotVersion
from app.schemas.robot import RobotCreate, RobotVersionCreate, SEMVER_REGEX

semver_pattern = re.compile(SEMVER_REGEX)


def is_valid_semver(version: str) -> bool:
    return bool(semver_pattern.match(version))


def get_robot(db: Session, robot_id: UUID) -> Robot | None:
    return db.scalar(
        select(Robot)
        .where(Robot.id == robot_id)
        .options(selectinload(Robot.versions), selectinload(Robot.tags), selectinload(Robot.release_tags))
    )


def create_robot(db: Session, payload: RobotCreate, created_by: UUID | None) -> Robot:
    robot = Robot(
        name=payload.name,
        description=payload.description,
        created_by=created_by,
    )
    db.add(robot)
    db.flush()

    for tag_value in sorted(set(payload.tags)):
        db.add(RobotTag(robot_id=robot.id, tag=tag_value))

    version = RobotVersion(
        robot_id=robot.id,
        version=payload.initial_version.version,
        channel=payload.initial_version.channel,
        artifact_type=payload.initial_version.artifact_type,
        artifact_path=payload.initial_version.artifact_path,
        artifact_sha256=payload.initial_version.artifact_sha256,
        changelog=payload.initial_version.changelog,
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
    db.flush()
    _set_release_tag(db, robot.id, "latest", version.id)
    _set_release_tag(db, robot.id, "stable", version.id)
    db.commit()

    query = (
        select(Robot)
        .where(Robot.id == robot.id)
        .options(selectinload(Robot.versions), selectinload(Robot.tags), selectinload(Robot.release_tags))
    )
    return db.scalar(query)


def list_robots(db: Session, skip: int = 0, limit: int = 50) -> tuple[list[Robot], int]:
    total = db.scalar(select(func.count()).select_from(Robot)) or 0
    robots = list(
        db.scalars(
            select(Robot)
            .order_by(Robot.created_at.desc())
            .options(selectinload(Robot.versions), selectinload(Robot.tags), selectinload(Robot.release_tags))
            .offset(skip)
            .limit(limit)
        )
    )
    return robots, total


def list_robots_scoped(db: Session, robot_ids: set[UUID], skip: int = 0, limit: int = 50) -> tuple[list[Robot], int]:
    if not robot_ids:
        return [], 0

    total = db.scalar(select(func.count()).select_from(Robot).where(Robot.id.in_(robot_ids))) or 0
    robots = list(
        db.scalars(
            select(Robot)
            .where(Robot.id.in_(robot_ids))
            .order_by(Robot.created_at.desc())
            .options(selectinload(Robot.versions), selectinload(Robot.tags), selectinload(Robot.release_tags))
            .offset(skip)
            .limit(limit)
        )
    )
    return robots, total


def add_robot_version(db: Session, robot_id: UUID, payload: RobotVersionCreate, created_by: UUID | None) -> RobotVersion:
    robot = db.scalar(select(Robot).where(Robot.id == robot_id))
    if not robot:
        raise ValueError("Robot not found.")
    if not is_valid_semver(payload.version):
        raise ValueError("Invalid semver.")

    existing = db.scalar(select(RobotVersion).where(RobotVersion.robot_id == robot_id, RobotVersion.version == payload.version))
    if existing:
        raise ValueError("Version already exists for this robot.")

    version = RobotVersion(
        robot_id=robot_id,
        version=payload.version,
        channel=payload.channel,
        artifact_type=payload.artifact_type,
        artifact_path=payload.artifact_path,
        artifact_sha256=payload.artifact_sha256,
        changelog=payload.changelog,
        entrypoint_type=payload.entrypoint_type,
        entrypoint_path=payload.entrypoint_path,
        arguments=payload.arguments,
        env_vars=payload.env_vars,
        working_directory=payload.working_directory,
        checksum=payload.checksum,
        created_by=created_by,
        is_active=payload.is_active,
    )
    if payload.is_active:
        db.query(RobotVersion).filter(RobotVersion.robot_id == robot_id).update({RobotVersion.is_active: False})
    db.add(version)
    db.flush()
    if payload.is_active:
        _set_release_tag(db, robot_id, "latest", version.id)
        if payload.channel == "stable":
            _set_release_tag(db, robot_id, "stable", version.id)
    db.commit()
    db.refresh(version)
    return version


def list_robot_versions(db: Session, robot_id: UUID) -> list[RobotVersion]:
    return list(
        db.scalars(
            select(RobotVersion)
            .where(RobotVersion.robot_id == robot_id)
            .order_by(RobotVersion.created_at.desc())
        )
    )


def publish_robot_version(
    db: Session,
    robot_id: UUID,
    version: str,
    channel: str,
    changelog: str | None,
    artifact_type: str,
    artifact_path: str,
    artifact_sha256: str,
    created_by: UUID | None,
    entrypoint_path: str,
    entrypoint_type: str = "PYTHON",
    arguments: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    working_directory: str | None = None,
) -> RobotVersion:
    robot = db.scalar(select(Robot).where(Robot.id == robot_id))
    if not robot:
        raise ValueError("Robot not found.")
    if not is_valid_semver(version):
        raise ValueError("Invalid semver.")

    existing = db.scalar(select(RobotVersion).where(RobotVersion.robot_id == robot_id, RobotVersion.version == version))
    if existing:
        raise ValueError("Version already exists for this robot.")

    db.query(RobotVersion).filter(RobotVersion.robot_id == robot_id).update({RobotVersion.is_active: False})
    published = RobotVersion(
        robot_id=robot_id,
        version=version,
        channel=channel,
        artifact_type=artifact_type,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        changelog=changelog,
        entrypoint_type=entrypoint_type,
        entrypoint_path=entrypoint_path,
        arguments=arguments or [],
        env_vars=env_vars or {},
        working_directory=working_directory,
        checksum=artifact_sha256,
        created_by=created_by,
        is_active=True,
    )
    db.add(published)
    db.flush()
    _set_release_tag(db, robot_id, "latest", published.id)
    if channel == "stable":
        _set_release_tag(db, robot_id, "stable", published.id)
    db.commit()
    db.refresh(published)
    return published


def activate_robot_version(db: Session, robot_id: UUID, version_id: UUID) -> RobotVersion:
    version = db.scalar(select(RobotVersion).where(RobotVersion.robot_id == robot_id, RobotVersion.id == version_id))
    if not version:
        raise ValueError("Version not found.")

    db.query(RobotVersion).filter(RobotVersion.robot_id == robot_id).update({RobotVersion.is_active: False})
    version.is_active = True
    db.flush()
    _set_release_tag(db, robot_id, "latest", version.id)
    if version.channel == "stable":
        _set_release_tag(db, robot_id, "stable", version.id)
    db.commit()
    db.refresh(version)
    return version


def get_robot_tags(db: Session, robot_id: UUID) -> set[str]:
    return set(db.scalars(select(RobotTag.tag).where(RobotTag.robot_id == robot_id)))


def update_robot_tags(db: Session, robot_id: UUID, tags: list[str]) -> Robot | None:
    robot = db.scalar(select(Robot).where(Robot.id == robot_id).options(selectinload(Robot.tags), selectinload(Robot.versions)))
    if not robot:
        return None

    normalized_tags = sorted(set(tag.strip() for tag in tags if tag.strip()))
    db.query(RobotTag).filter(RobotTag.robot_id == robot_id).delete()
    for tag in normalized_tags:
        db.add(RobotTag(robot_id=robot_id, tag=tag))
    db.commit()
    db.refresh(robot)
    return db.scalar(
        select(Robot)
        .where(Robot.id == robot_id)
        .options(selectinload(Robot.tags), selectinload(Robot.versions), selectinload(Robot.release_tags))
    )


def _set_release_tag(db: Session, robot_id: UUID, tag: str, version_id: UUID) -> None:
    existing = db.scalar(select(RobotReleaseTag).where(RobotReleaseTag.robot_id == robot_id, RobotReleaseTag.tag == tag))
    if existing:
        existing.version_id = version_id
        return
    db.add(RobotReleaseTag(robot_id=robot_id, tag=tag, version_id=version_id))
