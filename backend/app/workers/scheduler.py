from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.scheduler_service import run_scheduler_cycle

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger("enesa.scheduler")


def run_scheduler_once() -> None:
    db = SessionLocal()
    try:
        result = asyncio.run(run_scheduler_cycle(db=db))
        logger.info(
            "scheduler cycle complete dispatched=%s skipped_window=%s skipped_concurrency=%s skipped_duplicate=%s",
            result.dispatched_runs,
            result.skipped_window,
            result.skipped_concurrency,
            result.skipped_duplicate,
        )
    except Exception:  # noqa: BLE001
        logger.exception("scheduler cycle failed")
    finally:
        db.close()


def run_scheduler_forever() -> None:
    interval = max(5, settings.scheduler_interval_seconds)
    logger.info("scheduler started interval_seconds=%s", interval)
    while True:
        run_scheduler_once()
        time.sleep(interval)


if __name__ == "__main__":
    run_scheduler_forever()
