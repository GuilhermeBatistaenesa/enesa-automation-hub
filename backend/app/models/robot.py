from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EntryPointType(str, Enum):
    PYTHON = "PYTHON"
    EXE = "EXE"


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


class RobotVersion(Base):
    __tablename__ = "robot_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    robot_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("robots.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    entrypoint_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entrypoint_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    arguments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    env_vars: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    working_directory: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    robot: Mapped["Robot"] = relationship(back_populates="versions")
    runs: Mapped[list["Run"]] = relationship(back_populates="robot_version")

