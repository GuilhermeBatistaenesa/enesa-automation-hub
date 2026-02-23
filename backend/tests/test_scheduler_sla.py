from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_principal
from app.api.v1.endpoints import alerts as alerts_endpoint
from app.api.v1.endpoints import robots as robots_endpoint
from app.core.rbac import ALL_PERMISSIONS, Role
from app.db.base import Base
from app.db.session import get_db
from app.models.run import Run
from app.models.scheduler import AlertEvent, AlertType, TriggerType
from app.schemas.robot import RobotCreate, RobotVersionBase
from app.services import run_service
from app.services.identity_service import Principal
from app.services.robot_service import create_robot
from app.services.scheduler_service import create_sla_rule, run_scheduler_cycle, run_sla_monitor_cycle
from app.schemas.scheduler import SlaRuleCreate


def test_schedule_create_trigger_and_late_alert() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(robots_endpoint.router, prefix="/api/v1")
    app.include_router(alerts_endpoint.router, prefix="/api/v1")

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_principal() -> Principal:
        return Principal(
            subject="scheduler-admin",
            auth_source="local",
            role=Role.ADMIN,
            permissions=set(ALL_PERMISSIONS),
            user=None,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_principal] = override_principal

    with TestingSessionLocal() as db:
        robot = create_robot(
            db=db,
            created_by=None,
            payload=RobotCreate(
                name=f"scheduler-robot-{uuid4()}",
                description="scheduler test",
                tags=["ops"],
                initial_version=RobotVersionBase(
                    version="1.0.0",
                    channel="stable",
                    artifact_type="ZIP",
                    artifact_path="robots/scheduler/1.0.0/artifact.zip",
                    artifact_sha256="sha",
                    changelog="initial",
                    entrypoint_type="PYTHON",
                    entrypoint_path="main.py",
                    arguments=[],
                    env_vars={},
                    working_directory=None,
                    checksum="sha",
                ),
            ),
        )
        robot_id = robot.id

    client = TestClient(app)
    schedule_response = client.post(
        f"/api/v1/robots/{robot_id}/schedule",
        json={
            "enabled": True,
            "cron_expr": "* * * * *",
            "timezone": "America/Sao_Paulo",
            "window_start": None,
            "window_end": None,
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "retry_count": 1,
            "retry_backoff_seconds": 10,
        },
    )
    assert schedule_response.status_code == 201

    queued_payloads: list[dict] = []

    async def fake_enqueue(payload: dict) -> None:
        queued_payloads.append(payload)

    original_enqueue = run_service.enqueue_run
    run_service.enqueue_run = fake_enqueue
    try:
        with TestingSessionLocal() as db:
            result = asyncio.run(run_scheduler_cycle(db=db, now_utc=datetime.now(timezone.utc).replace(second=0, microsecond=0)))
            assert result.dispatched_runs == 1

            created_run = db.scalar(select(Run).where(Run.robot_id == robot_id).order_by(Run.queued_at.desc()))
            assert created_run is not None
            assert created_run.trigger_type == TriggerType.SCHEDULED.value
            assert created_run.attempt == 1
            assert created_run.schedule_id is not None
        assert len(queued_payloads) == 1
    finally:
        run_service.enqueue_run = original_enqueue

    with TestingSessionLocal() as db:
        create_sla_rule(
            db=db,
            robot_id=robot_id,
            created_by=None,
            payload=SlaRuleCreate(
                expected_run_every_minutes=1,
                expected_daily_time=None,
                late_after_minutes=1,
                alert_on_failure=True,
                alert_on_late=True,
                notify_channels_json={},
            ),
        )
        db.query(Run).delete()
        db.commit()

        sla_result = run_sla_monitor_cycle(db=db, now_utc=datetime.now(timezone.utc))
        assert sla_result.created_alerts >= 1
        late_alert = db.scalar(
            select(AlertEvent).where(AlertEvent.robot_id == robot_id, AlertEvent.type == AlertType.LATE.value)
        )
        assert late_alert is not None
