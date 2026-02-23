from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.artifact import Artifact
from app.models.run import RunLog

settings = get_settings()


@dataclass(slots=True)
class CleanupResult:
    removed_log_rows: int
    removed_artifact_rows: int
    removed_artifact_files: int


def execute_retention_cleanup(db: Session) -> CleanupResult:
    now = datetime.now(timezone.utc)
    log_cutoff = now - timedelta(days=settings.log_retention_days)
    artifact_cutoff = now - timedelta(days=settings.artifact_retention_days)

    artifact_rows = list(db.scalars(select(Artifact).where(Artifact.created_at < artifact_cutoff)))
    removed_files = 0
    for artifact in artifact_rows:
        path = Path(artifact.file_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
            removed_files += 1

    removed_artifacts = db.execute(delete(Artifact).where(Artifact.created_at < artifact_cutoff)).rowcount or 0
    removed_logs = db.execute(delete(RunLog).where(RunLog.timestamp < log_cutoff)).rowcount or 0
    db.commit()

    return CleanupResult(
        removed_log_rows=removed_logs,
        removed_artifact_rows=removed_artifacts,
        removed_artifact_files=removed_files,
    )

