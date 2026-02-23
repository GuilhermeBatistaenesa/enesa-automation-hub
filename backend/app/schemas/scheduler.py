from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class ScheduleBase(BaseModel):
    enabled: bool = True
    cron_expr: str = Field(..., min_length=5, max_length=120)
    timezone: str = Field(default="America/Sao_Paulo", min_length=3, max_length=80)
    window_start: str | None = Field(default=None, pattern=TIME_PATTERN)
    window_end: str | None = Field(default=None, pattern=TIME_PATTERN)
    max_concurrency: int = Field(default=1, ge=1, le=100)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    retry_count: int = Field(default=0, ge=0, le=10)
    retry_backoff_seconds: int = Field(default=60, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_window(self) -> "ScheduleBase":
        if bool(self.window_start) ^ bool(self.window_end):
            raise ValueError("window_start and window_end must be informed together.")
        return self


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cron_expr: str | None = Field(default=None, min_length=5, max_length=120)
    timezone: str | None = Field(default=None, min_length=3, max_length=80)
    window_start: str | None = Field(default=None, pattern=TIME_PATTERN)
    window_end: str | None = Field(default=None, pattern=TIME_PATTERN)
    max_concurrency: int | None = Field(default=None, ge=1, le=100)
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    retry_count: int | None = Field(default=None, ge=0, le=10)
    retry_backoff_seconds: int | None = Field(default=None, ge=1, le=3600)


class ScheduleRead(ORMModel):
    id: UUID
    robot_id: UUID
    enabled: bool
    cron_expr: str
    timezone: str
    window_start: str | None
    window_end: str | None
    max_concurrency: int
    timeout_seconds: int
    retry_count: int
    retry_backoff_seconds: int
    created_by: UUID | None
    created_at: datetime


class SlaRuleBase(BaseModel):
    expected_run_every_minutes: int | None = Field(default=None, ge=1, le=10080)
    expected_daily_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    late_after_minutes: int = Field(default=15, ge=1, le=720)
    alert_on_failure: bool = True
    alert_on_late: bool = True
    notify_channels_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_expectation(self) -> "SlaRuleBase":
        if not self.expected_run_every_minutes and not self.expected_daily_time:
            raise ValueError("Provide expected_run_every_minutes or expected_daily_time.")
        return self


class SlaRuleCreate(SlaRuleBase):
    pass


class SlaRuleUpdate(BaseModel):
    expected_run_every_minutes: int | None = Field(default=None, ge=1, le=10080)
    expected_daily_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    late_after_minutes: int | None = Field(default=None, ge=1, le=720)
    alert_on_failure: bool | None = None
    alert_on_late: bool | None = None
    notify_channels_json: dict[str, Any] | None = None


class SlaRuleRead(ORMModel):
    id: UUID
    robot_id: UUID
    expected_run_every_minutes: int | None
    expected_daily_time: str | None
    late_after_minutes: int
    alert_on_failure: bool
    alert_on_late: bool
    notify_channels_json: dict[str, Any]
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class AlertEventRead(ORMModel):
    id: UUID
    robot_id: UUID
    run_id: UUID | None
    type: str
    severity: str
    message: str
    metadata_json: dict[str, Any]
    created_at: datetime
    resolved_at: datetime | None
