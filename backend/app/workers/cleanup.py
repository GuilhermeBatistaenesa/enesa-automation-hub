from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.retention_service import execute_retention_cleanup

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger(__name__)


def run_cleanup_once() -> None:
    db = SessionLocal()
    try:
        result = execute_retention_cleanup(db)
        logger.info(
            "Cleanup concluido",
            extra={
                "removed_log_rows": result.removed_log_rows,
                "removed_artifact_rows": result.removed_artifact_rows,
                "removed_artifact_files": result.removed_artifact_files,
            },
        )
    finally:
        db.close()


def run_cleanup_scheduler() -> None:
    interval_seconds = max(1, settings.cleanup_interval_hours) * 3600
    logger.info("Cleanup scheduler iniciado com intervalo de %s segundos", interval_seconds)
    while True:
        run_cleanup_once()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_cleanup_scheduler()
