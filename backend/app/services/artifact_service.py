from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import Artifact


def get_artifact(db: Session, run_id: UUID, artifact_id: UUID) -> Artifact | None:
    return db.scalar(select(Artifact).where(Artifact.run_id == run_id, Artifact.id == artifact_id))


def resolve_artifact_path(artifact: Artifact) -> Path:
    return Path(artifact.file_path)

