from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.scheduler_service import run_sla_monitor_cycle

settings = get_settings()
configure_logging(level=getattr(logging, settings.log_level.upper(), logging.INFO), log_format=settings.log_format)
logger = logging.getLogger("enesa.sla_monitor")


def run_sla_monitor_once() -> None:
    db = SessionLocal()
    try:
        result = run_sla_monitor_cycle(db=db)
        logger.info("sla cycle complete checked_rules=%s created_alerts=%s", result.checked_rules, result.created_alerts)
    except Exception:  # noqa: BLE001
        logger.exception("sla monitor cycle failed")
    finally:
        db.close()


def run_sla_monitor_forever() -> None:
    interval = max(30, settings.sla_monitor_interval_seconds)
    logger.info("sla monitor started interval_seconds=%s", interval)
    while True:
        run_sla_monitor_once()
        time.sleep(interval)


if __name__ == "__main__":
    run_sla_monitor_forever()
