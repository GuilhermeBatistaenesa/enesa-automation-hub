from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.robot import Robot
from app.models.run import Run, RunStatus
from app.models.scheduler import AlertEvent, AlertSeverity, AlertType, Schedule, SlaRule, TriggerType
from app.schemas.run import RunExecuteRequest
from app.schemas.scheduler import ScheduleCreate, ScheduleUpdate, SlaRuleCreate, SlaRuleUpdate
from app.services.audit_service import log_audit_event
from app.services.queue_service import get_queue_depth_sync, list_worker_heartbeats
from app.services.run_service import create_run_and_enqueue

settings = get_settings()
logger = logging.getLogger(__name__)

_local_schedule_locks: dict[str, threading.Lock] = {}
_cron_field_regex = re.compile(r"^(\*|\d+|\d+-\d+)(/\d+)?$")


@dataclass(slots=True)
class SchedulerCycleResult:
    dispatched_runs: int
    skipped_window: int
    skipped_concurrency: int
    skipped_duplicate: int


@dataclass(slots=True)
class SlaCycleResult:
    created_alerts: int
    checked_rules: int


def get_schedule(db: Session, robot_id: UUID) -> Schedule | None:
    return db.scalar(select(Schedule).where(Schedule.robot_id == robot_id))


def create_schedule(db: Session, robot_id: UUID, payload: ScheduleCreate, created_by: UUID | None) -> Schedule:
    _validate_schedule_payload(payload.cron_expr, payload.timezone, payload.window_start, payload.window_end)
    robot = db.scalar(select(Robot).where(Robot.id == robot_id))
    if not robot:
        raise ValueError("Robot not found.")
    existing = get_schedule(db=db, robot_id=robot_id)
    if existing:
        raise ValueError("Robot already has a schedule.")

    schedule = Schedule(
        robot_id=robot_id,
        enabled=payload.enabled,
        cron_expr=payload.cron_expr,
        timezone=payload.timezone,
        window_start=payload.window_start,
        window_end=payload.window_end,
        max_concurrency=payload.max_concurrency,
        timeout_seconds=payload.timeout_seconds,
        retry_count=payload.retry_count,
        retry_backoff_seconds=payload.retry_backoff_seconds,
        created_by=created_by,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(db: Session, robot_id: UUID, payload: ScheduleUpdate) -> Schedule:
    schedule = get_schedule(db=db, robot_id=robot_id)
    if not schedule:
        raise ValueError("Schedule not found.")

    cron_expr = payload.cron_expr if payload.cron_expr is not None else schedule.cron_expr
    tz_name = payload.timezone if payload.timezone is not None else schedule.timezone
    window_start = payload.window_start if payload.window_start is not None else schedule.window_start
    window_end = payload.window_end if payload.window_end is not None else schedule.window_end
    _validate_schedule_payload(cron_expr, tz_name, window_start, window_end)

    for field in (
        "enabled",
        "cron_expr",
        "timezone",
        "window_start",
        "window_end",
        "max_concurrency",
        "timeout_seconds",
        "retry_count",
        "retry_backoff_seconds",
    ):
        if field in payload.model_fields_set:
            setattr(schedule, field, getattr(payload, field))

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, robot_id: UUID) -> None:
    schedule = get_schedule(db=db, robot_id=robot_id)
    if not schedule:
        raise ValueError("Schedule not found.")
    db.delete(schedule)
    db.commit()


def get_sla_rule(db: Session, robot_id: UUID) -> SlaRule | None:
    return db.scalar(select(SlaRule).where(SlaRule.robot_id == robot_id))


def create_sla_rule(db: Session, robot_id: UUID, payload: SlaRuleCreate, created_by: UUID | None) -> SlaRule:
    robot = db.scalar(select(Robot).where(Robot.id == robot_id))
    if not robot:
        raise ValueError("Robot not found.")
    existing = get_sla_rule(db=db, robot_id=robot_id)
    if existing:
        raise ValueError("Robot already has an SLA rule.")

    _validate_sla_payload(payload.expected_run_every_minutes, payload.expected_daily_time)

    rule = SlaRule(
        robot_id=robot_id,
        expected_run_every_minutes=payload.expected_run_every_minutes,
        expected_daily_time=payload.expected_daily_time,
        late_after_minutes=payload.late_after_minutes,
        alert_on_failure=payload.alert_on_failure,
        alert_on_late=payload.alert_on_late,
        notify_channels_json=payload.notify_channels_json,
        created_by=created_by,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_sla_rule(db: Session, robot_id: UUID, payload: SlaRuleUpdate) -> SlaRule:
    rule = get_sla_rule(db=db, robot_id=robot_id)
    if not rule:
        raise ValueError("SLA rule not found.")

    expected_run_every = payload.expected_run_every_minutes if payload.expected_run_every_minutes is not None else rule.expected_run_every_minutes
    expected_daily_time = payload.expected_daily_time if payload.expected_daily_time is not None else rule.expected_daily_time
    _validate_sla_payload(expected_run_every, expected_daily_time)

    for field in (
        "expected_run_every_minutes",
        "expected_daily_time",
        "late_after_minutes",
        "alert_on_failure",
        "alert_on_late",
        "notify_channels_json",
    ):
        if field in payload.model_fields_set:
            setattr(rule, field, getattr(payload, field))

    db.commit()
    db.refresh(rule)
    return rule


def list_alerts(
    db: Session,
    status: str | None = None,
    alert_type: str | None = None,
    robot_id: UUID | None = None,
    limit: int = 200,
) -> list[AlertEvent]:
    stmt = select(AlertEvent).order_by(AlertEvent.created_at.desc())
    if status == "open":
        stmt = stmt.where(AlertEvent.resolved_at.is_(None))
    elif status == "resolved":
        stmt = stmt.where(AlertEvent.resolved_at.is_not(None))
    if alert_type:
        stmt = stmt.where(AlertEvent.type == alert_type)
    if robot_id:
        stmt = stmt.where(AlertEvent.robot_id == robot_id)
    return list(db.scalars(stmt.limit(limit)))


def resolve_alert(db: Session, alert_id: UUID) -> AlertEvent:
    alert = db.scalar(select(AlertEvent).where(AlertEvent.id == alert_id))
    if not alert:
        raise ValueError("Alert not found.")
    if not alert.resolved_at:
        alert.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
    return alert


def create_alert_if_needed(
    db: Session,
    robot_id: UUID,
    alert_type: str,
    severity: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    run_id: UUID | None = None,
) -> AlertEvent | None:
    open_existing = db.scalar(
        select(AlertEvent).where(
            AlertEvent.robot_id == robot_id,
            AlertEvent.type == alert_type,
            AlertEvent.resolved_at.is_(None),
        )
    )
    if open_existing:
        return None

    alert = AlertEvent(
        robot_id=robot_id,
        run_id=run_id,
        type=alert_type,
        severity=severity,
        message=message,
        metadata_json=metadata or {},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    log_audit_event(
        db=db,
        action="alert.created",
        principal=None,
        actor_ip=None,
        target_type="alert",
        target_id=str(alert.id),
        metadata={
            "robot_id": str(robot_id),
            "run_id": str(run_id) if run_id else None,
            "type": alert_type,
            "severity": severity,
        },
    )
    _send_notification_placeholder(alert=alert)
    return alert


async def run_scheduler_cycle(db: Session, now_utc: datetime | None = None) -> SchedulerCycleResult:
    now_utc = now_utc or datetime.now(timezone.utc)
    schedules = list(db.scalars(select(Schedule).where(Schedule.enabled.is_(True))))

    dispatched = 0
    skipped_window = 0
    skipped_concurrency = 0
    skipped_duplicate = 0

    for schedule in schedules:
        if not _is_schedule_due(schedule=schedule, now_utc=now_utc):
            continue
        if not _inside_execution_window(schedule=schedule, now_utc=now_utc):
            skipped_window += 1
            continue

        lock_key = f"schedule-dispatch:{schedule.robot_id}"
        if not _acquire_robot_lock(db=db, lock_key=lock_key):
            continue
        try:
            if _already_dispatched_this_minute(db=db, schedule_id=schedule.id, now_utc=now_utc):
                skipped_duplicate += 1
                continue

            active = db.scalar(
                select(func.count()).select_from(Run).where(
                    Run.robot_id == schedule.robot_id,
                    Run.status.in_([RunStatus.PENDING.value, RunStatus.RUNNING.value]),
                )
            ) or 0
            if active >= schedule.max_concurrency:
                skipped_concurrency += 1
                continue

            try:
                run = await create_run_and_enqueue(
                    db=db,
                    robot_id=schedule.robot_id,
                    payload=RunExecuteRequest(runtime_arguments=[], runtime_env={}),
                    triggered_by=schedule.created_by,
                    trigger_type=TriggerType.SCHEDULED.value,
                    attempt=1,
                    schedule_id=schedule.id,
                )
                log_audit_event(
                    db=db,
                    action="schedule.dispatched",
                    principal=None,
                    actor_ip=None,
                    target_type="run",
                    target_id=str(run.run_id),
                    metadata={
                        "run_id": str(run.run_id),
                        "robot_id": str(schedule.robot_id),
                        "schedule_id": str(schedule.id),
                        "trigger_type": TriggerType.SCHEDULED.value,
                    },
                )
                dispatched += 1
            except ValueError as exc:
                logger.warning("Failed to dispatch scheduled run for robot %s: %s", schedule.robot_id, exc)
        finally:
            _release_robot_lock(db=db, lock_key=lock_key)

    return SchedulerCycleResult(
        dispatched_runs=dispatched,
        skipped_window=skipped_window,
        skipped_concurrency=skipped_concurrency,
        skipped_duplicate=skipped_duplicate,
    )


def run_sla_monitor_cycle(db: Session, now_utc: datetime | None = None) -> SlaCycleResult:
    now_utc = now_utc or datetime.now(timezone.utc)
    rules = list(db.scalars(select(SlaRule)))
    created = 0

    for rule in rules:
        if rule.alert_on_late and _is_robot_late(db=db, rule=rule, now_utc=now_utc):
            created += int(
                create_alert_if_needed(
                    db=db,
                    robot_id=rule.robot_id,
                    alert_type=AlertType.LATE.value,
                    severity=AlertSeverity.WARN.value,
                    message=f"Robot {rule.robot_id} is late based on configured SLA.",
                    metadata={
                        "expected_run_every_minutes": rule.expected_run_every_minutes,
                        "expected_daily_time": rule.expected_daily_time,
                        "late_after_minutes": rule.late_after_minutes,
                    },
                )
                is not None
            )

        if rule.alert_on_failure and _has_failure_streak(db=db, robot_id=rule.robot_id, threshold=settings.failure_streak_threshold):
            created += int(
                create_alert_if_needed(
                    db=db,
                    robot_id=rule.robot_id,
                    alert_type=AlertType.FAILURE_STREAK.value,
                    severity=AlertSeverity.CRITICAL.value,
                    message=f"Robot {rule.robot_id} reached failure streak >= {settings.failure_streak_threshold}.",
                    metadata={"failure_streak_threshold": settings.failure_streak_threshold},
                )
                is not None
            )

    created += _evaluate_queue_backlog(db=db)
    created += _evaluate_worker_down(db=db, now_utc=now_utc)
    return SlaCycleResult(created_alerts=created, checked_rules=len(rules))


def _evaluate_queue_backlog(db: Session) -> int:
    depth = get_queue_depth_sync()
    if depth <= settings.queue_backlog_alert_threshold:
        return 0
    robot_id = _pick_robot_for_system_alert(db)
    if not robot_id:
        return 0
    return int(
        create_alert_if_needed(
            db=db,
            robot_id=robot_id,
            alert_type=AlertType.QUEUE_BACKLOG.value,
            severity=AlertSeverity.WARN.value,
            message=f"Queue depth is high ({depth}).",
            metadata={"queue_depth": depth, "threshold": settings.queue_backlog_alert_threshold},
        )
        is not None
    )


def _evaluate_worker_down(db: Session, now_utc: datetime) -> int:
    heartbeats = list_worker_heartbeats()
    now_ts = now_utc.timestamp()
    stale = [worker for worker, ts in heartbeats.items() if now_ts - ts > settings.worker_stale_seconds]
    if stale:
        robot_id = _pick_robot_for_system_alert(db)
        if not robot_id:
            return 0
        return int(
            create_alert_if_needed(
                db=db,
                robot_id=robot_id,
                alert_type=AlertType.WORKER_DOWN.value,
                severity=AlertSeverity.CRITICAL.value,
                message="Worker heartbeat is stale.",
                metadata={"stale_workers": stale, "stale_after_seconds": settings.worker_stale_seconds},
            )
            is not None
        )
    return 0


def _pick_robot_for_system_alert(db: Session) -> UUID | None:
    schedule_robot = db.scalar(select(Schedule.robot_id).where(Schedule.enabled.is_(True)).limit(1))
    if schedule_robot:
        return schedule_robot
    any_robot = db.scalar(select(Robot.id).limit(1))
    return any_robot


def _is_robot_late(db: Session, rule: SlaRule, now_utc: datetime) -> bool:
    last_run = db.scalar(
        select(Run)
        .where(Run.robot_id == rule.robot_id)
        .order_by(Run.queued_at.desc())
        .limit(1)
    )

    if rule.expected_run_every_minutes:
        if not last_run:
            return True
        elapsed_minutes = (now_utc - last_run.queued_at).total_seconds() / 60
        return elapsed_minutes > (rule.expected_run_every_minutes + rule.late_after_minutes)

    if rule.expected_daily_time:
        tz_name = _safe_timezone_name(rule.robot.schedule.timezone if rule.robot and rule.robot.schedule else settings.app_timezone)
        tz = ZoneInfo(tz_name)
        local_now = now_utc.astimezone(tz)
        target_time = _parse_hhmm(rule.expected_daily_time)
        expected_local = datetime.combine(local_now.date(), target_time, tzinfo=tz)
        late_local = expected_local + timedelta(minutes=rule.late_after_minutes)
        if local_now <= late_local:
            return False

        expected_utc = expected_local.astimezone(timezone.utc)
        run_since_expected = db.scalar(
            select(func.count())
            .select_from(Run)
            .where(and_(Run.robot_id == rule.robot_id, Run.queued_at >= expected_utc))
        ) or 0
        return run_since_expected == 0

    return False


def _has_failure_streak(db: Session, robot_id: UUID, threshold: int) -> bool:
    if threshold <= 0:
        return False
    runs = list(
        db.scalars(
            select(Run)
            .where(Run.robot_id == robot_id)
            .order_by(Run.queued_at.desc())
            .limit(threshold)
        )
    )
    if len(runs) < threshold:
        return False
    return all(item.status == RunStatus.FAILED.value for item in runs)


def _is_schedule_due(schedule: Schedule, now_utc: datetime) -> bool:
    tz_name = _safe_timezone_name(schedule.timezone)
    local_now = now_utc.astimezone(ZoneInfo(tz_name))
    return _cron_matches(schedule.cron_expr, local_now)


def _inside_execution_window(schedule: Schedule, now_utc: datetime) -> bool:
    if not schedule.window_start or not schedule.window_end:
        return True
    tz_name = _safe_timezone_name(schedule.timezone)
    local_now = now_utc.astimezone(ZoneInfo(tz_name))
    now_t = local_now.time()
    start = _parse_hhmm(schedule.window_start)
    end = _parse_hhmm(schedule.window_end)
    if start <= end:
        return start <= now_t <= end
    return now_t >= start or now_t <= end


def _already_dispatched_this_minute(db: Session, schedule_id: UUID, now_utc: datetime) -> bool:
    minute_start = now_utc.replace(second=0, microsecond=0)
    minute_end = minute_start + timedelta(minutes=1)
    existing = db.scalar(
        select(func.count())
        .select_from(Run)
        .where(
            Run.schedule_id == schedule_id,
            Run.trigger_type == TriggerType.SCHEDULED.value,
            Run.queued_at >= minute_start,
            Run.queued_at < minute_end,
        )
    ) or 0
    return existing > 0


def _acquire_robot_lock(db: Session, lock_key: str) -> bool:
    if db.bind and db.bind.dialect.name.startswith("mssql"):
        try:
            row = db.execute(
                text(
                    """
                    DECLARE @result INT;
                    EXEC @result = sp_getapplock
                        @Resource = :resource,
                        @LockMode = 'Exclusive',
                        @LockOwner = 'Transaction',
                        @LockTimeout = 0;
                    SELECT @result AS result;
                    """
                ),
                {"resource": lock_key},
            ).mappings().first()
            return bool(row and row["result"] >= 0)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to acquire SQL lock for %s", lock_key)
            return False

    lock = _local_schedule_locks.setdefault(lock_key, threading.Lock())
    return lock.acquire(blocking=False)


def _release_robot_lock(db: Session, lock_key: str) -> None:
    if db.bind and db.bind.dialect.name.startswith("mssql"):
        # Transaction-scoped SQL locks are released on commit/rollback.
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to rollback lock transaction for %s", lock_key)
        return

    lock = _local_schedule_locks.get(lock_key)
    if lock and lock.locked():
        lock.release()


def _cron_matches(expr: str, local_dt: datetime) -> bool:
    fields = expr.split()
    if len(fields) != 5:
        return False

    minute, hour, day, month, dow = fields
    cron_dow = local_dt.isoweekday() % 7  # Sunday=0
    return (
        _match_cron_field(minute, local_dt.minute, 0, 59)
        and _match_cron_field(hour, local_dt.hour, 0, 23)
        and _match_cron_field(day, local_dt.day, 1, 31)
        and _match_cron_field(month, local_dt.month, 1, 12)
        and _match_cron_field(dow, cron_dow, 0, 7, is_day_of_week=True)
    )


def _match_cron_field(raw: str, value: int, min_value: int, max_value: int, is_day_of_week: bool = False) -> bool:
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            return True
        if not _cron_field_regex.match(part):
            return False

        step = 1
        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
        else:
            base = part

        if base == "*":
            if (value - min_value) % step == 0:
                return True
            continue

        if "-" in base:
            start_text, end_text = base.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if is_day_of_week:
                start = 0 if start == 7 else start
                end = 0 if end == 7 else end
            if start > end:
                return False
            if start <= value <= end and (value - start) % step == 0:
                return True
            continue

        num = int(base)
        if is_day_of_week and num == 7:
            num = 0
        if num == value:
            return True
    return False


def _parse_hhmm(value: str) -> time:
    hour_str, minute_str = value.split(":")
    return time(hour=int(hour_str), minute=int(minute_str))


def _safe_timezone_name(value: str | None) -> str:
    candidate = value or settings.app_timezone
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:  # noqa: BLE001
        return settings.app_timezone


def _validate_schedule_payload(cron_expr: str, timezone_name: str, window_start: str | None, window_end: str | None) -> None:
    if len(cron_expr.split()) != 5:
        raise ValueError("cron_expr must have exactly 5 fields.")
    probe_dt = datetime.now(timezone.utc).astimezone(ZoneInfo(_safe_timezone_name(timezone_name)))
    if not _cron_matches(cron_expr, probe_dt):
        # still valid even if current moment does not match; use syntax-only validation below.
        pass

    for field in cron_expr.split():
        for part in field.split(","):
            if part.strip() == "*":
                continue
            if not _cron_field_regex.match(part.strip()):
                raise ValueError("cron_expr contains invalid field syntax.")

    if bool(window_start) ^ bool(window_end):
        raise ValueError("window_start and window_end must be informed together.")
    if window_start and window_end:
        _parse_hhmm(window_start)
        _parse_hhmm(window_end)


def _validate_sla_payload(expected_run_every_minutes: int | None, expected_daily_time: str | None) -> None:
    if not expected_run_every_minutes and not expected_daily_time:
        raise ValueError("Provide expected_run_every_minutes or expected_daily_time.")
    if expected_daily_time:
        _parse_hhmm(expected_daily_time)


def _send_notification_placeholder(alert: AlertEvent) -> None:
    logger.warning(
        "ALERT_NOTIFICATION_PLACEHOLDER type=%s severity=%s robot_id=%s run_id=%s message=%s",
        alert.type,
        alert.severity,
        alert.robot_id,
        alert.run_id,
        alert.message,
    )
