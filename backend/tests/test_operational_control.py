from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_principal
from app.api.v1.endpoints import runs as runs_endpoint
from app.api.v1.endpoints import workers as workers_endpoint
from app.core.rbac import PERMISSION_ROBOT_RUN, PERMISSION_WORKER_MANAGE, Role
from app.db.base import Base
from app.db.session import get_db
from app.models.run import Run, RunStatus
from app.models.worker import Worker, WorkerStatus
from app.schemas.robot import RobotCreate, RobotVersionBase
from app.services.identity_service import Principal
from app.services.robot_service import create_robot


def _setup_test_context() -> tuple[FastAPI, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(runs_endpoint.router, prefix="/api/v1")
    app.include_router(workers_endpoint.router, prefix="/api/v1")

    def override_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return app, testing_session_local


def test_cancel_running_run_is_idempotent() -> None:
    app, testing_session_local = _setup_test_context()

    def override_principal() -> Principal:
        return Principal(
            subject="operator-subject",
            auth_source="local",
            role=Role.OPERATOR,
            permissions={PERMISSION_ROBOT_RUN},
            user=None,
        )

    app.dependency_overrides[get_current_principal] = override_principal

    with testing_session_local() as db:
        robot = create_robot(
            db=db,
            created_by=None,
            payload=RobotCreate(
                name=f"cancel-robot-{uuid4()}",
                description="cancel test",
                tags=["qa"],
                initial_version=RobotVersionBase(
                    version="1.0.0",
                    channel="stable",
                    artifact_type="ZIP",
                    artifact_path="robots/cancel/1.0.0/artifact.zip",
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
        run = Run(
            robot_id=robot.id,
            robot_version_id=robot.versions[0].id,
            status=RunStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc),
            triggered_by=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.run_id

    client = TestClient(app)
    response = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["cancel_requested"] is True
    assert body["status"] == RunStatus.RUNNING.value

    second = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert second.status_code == 200
    assert second.json()["cancel_requested"] is True

    with testing_session_local() as db:
        stored = db.scalar(select(Run).where(Run.run_id == run_id))
        assert stored is not None
        assert stored.cancel_requested is True


def test_pause_and_resume_worker() -> None:
    app, testing_session_local = _setup_test_context()

    def override_principal() -> Principal:
        return Principal(
            subject="admin-subject",
            auth_source="local",
            role=Role.ADMIN,
            permissions={PERMISSION_WORKER_MANAGE},
            user=None,
        )

    app.dependency_overrides[get_current_principal] = override_principal

    worker_id = uuid4()
    with testing_session_local() as db:
        db.add(
            Worker(
                id=worker_id,
                hostname="test-host",
                status=WorkerStatus.RUNNING.value,
                last_heartbeat=datetime.now(timezone.utc),
                version="2.0.0",
            )
        )
        db.commit()

    client = TestClient(app)
    paused = client.post(f"/api/v1/workers/{worker_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == WorkerStatus.PAUSED.value

    resumed = client.post(f"/api/v1/workers/{worker_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == WorkerStatus.RUNNING.value
