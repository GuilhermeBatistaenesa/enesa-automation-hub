from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EntryPointType(str, Enum):
    PYTHON = "PYTHON"
    EXE = "EXE"


class ArtifactType(str, Enum):
    ZIP = "ZIP"
    EXE = "EXE"


class ReleaseChannel(str, Enum):
    STABLE = "stable"
    BETA = "beta"
    HOTFIX = "hotfix"


class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    versions: Mapped[list["RobotVersion"]] = relationship(back_populates="robot", cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(back_populates="robot")
    services: Mapped[list["Service"]] = relationship(back_populates="robot")
    tags: Mapped[list["RobotTag"]] = relationship(back_populates="robot", cascade="all, delete-orphan")
    release_tags: Mapped[list["RobotReleaseTag"]] = relationship(back_populates="robot", cascade="all, delete-orphan")


class RobotVersion(Base):
    __tablename__ = "robot_versions"
    __table_args__ = (UniqueConstraint("robot_id", "version", name="uq_robot_versions_robot_id_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    robot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("robots.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default=ReleaseChannel.STABLE.value)
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ArtifactType.ZIP.value)
    artifact_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)

    entrypoint_type: Mapped[str] = mapped_column(String(20), nullable=False, default=EntryPointType.PYTHON.value)
    entrypoint_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="main.py")
    arguments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    env_vars: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    working_directory: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    robot: Mapped["Robot"] = relationship(back_populates="versions")
    runs: Mapped[list["Run"]] = relationship(back_populates="robot_version")


class RobotTag(Base):
    __tablename__ = "robot_tags"
    __table_args__ = (UniqueConstraint("robot_id", "tag", name="uq_robot_tags_robot_id_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    robot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("robots.id", ondelete="CASCADE"), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    robot: Mapped["Robot"] = relationship(back_populates="tags")


class RobotReleaseTag(Base):
    __tablename__ = "robot_release_tags"
    __table_args__ = (UniqueConstraint("robot_id", "tag", name="uq_robot_release_tags_robot_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    robot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("robots.id", ondelete="CASCADE"), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("robot_versions.id", ondelete="CASCADE"), nullable=False)

    robot: Mapped["Robot"] = relationship(back_populates="release_tags")
