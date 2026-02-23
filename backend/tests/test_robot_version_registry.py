from __future__ import annotations

import io
import uuid
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_principal
from app.api.v1.endpoints import robots as robots_endpoint
from app.core.config import get_settings
from app.core.rbac import PERMISSION_ROBOT_PUBLISH, PERMISSION_ROBOT_READ, Role
from app.db.base import Base
from app.db.session import get_db
from app.models.robot import RobotVersion
from app.schemas.robot import RobotCreate, RobotVersionBase
from app.services.identity_service import Principal
from app.services.robot_service import create_robot


def _zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("main.py", "print('registry test')\n")
    return buffer.getvalue()


def test_publish_list_activate_registry(tmp_path) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    settings = get_settings()
    original_artifacts_root = settings.artifacts_root
    settings.artifacts_root = tmp_path

    app = FastAPI()
    app.include_router(robots_endpoint.router, prefix="/api/v1")

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_principal() -> Principal:
        return Principal(
            subject="test-subject",
            auth_source="local",
            role=Role.MAINTAINER,
            permissions={PERMISSION_ROBOT_PUBLISH, PERMISSION_ROBOT_READ},
            user=None,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_principal] = override_principal

    with TestingSessionLocal() as db:
        robot = create_robot(
            db=db,
            created_by=None,
            payload=RobotCreate(
                name="robot-registry-test",
                description="registry",
                tags=["qa"],
                initial_version=RobotVersionBase(
                    version="1.0.0",
                    channel="stable",
                    artifact_type="ZIP",
                    artifact_path=str(tmp_path / "robots" / "dummy" / "1.0.0" / "artifact.zip"),
                    artifact_sha256="oldsha",
                    changelog="initial",
                    entrypoint_type="PYTHON",
                    entrypoint_path="main.py",
                    arguments=[],
                    env_vars={},
                    working_directory=None,
                    checksum="oldsha",
                ),
            ),
        )
        initial_version_id = robot.versions[0].id
        robot_id = robot.id

    client = TestClient(app)

    publish_response = client.post(
        f"/api/v1/robots/{robot_id}/versions/publish",
        data={
            "version": "1.1.0",
            "channel": "stable",
            "changelog": "new release",
            "entrypoint_path": "main.py",
            "entrypoint_type": "PYTHON",
        },
        files={"artifact": ("artifact.zip", _zip_payload(), "application/zip")},
    )
    assert publish_response.status_code == 201
    published = publish_response.json()
    assert published["version"] == "1.1.0"
    assert published["artifact_type"] == "ZIP"
    assert published["is_active"] is True
    assert published["artifact_sha256"]

    duplicate_response = client.post(
        f"/api/v1/robots/{robot_id}/versions/publish",
        data={
            "version": "1.1.0",
            "channel": "stable",
            "entrypoint_path": "main.py",
            "entrypoint_type": "PYTHON",
        },
        files={"artifact": ("artifact.zip", _zip_payload(), "application/zip")},
    )
    assert duplicate_response.status_code == 400

    list_response = client.get(f"/api/v1/robots/{robot_id}/versions")
    assert list_response.status_code == 200
    versions = list_response.json()
    assert len(versions) >= 2
    assert any(item["version"] == "1.1.0" for item in versions)

    activate_response = client.post(f"/api/v1/robots/{robot_id}/versions/{initial_version_id}/activate")
    assert activate_response.status_code == 200
    activated = activate_response.json()
    assert activated["id"] == str(initial_version_id)
    assert activated["is_active"] is True

    with TestingSessionLocal() as db:
        active_versions = list(
            db.scalars(
                select(RobotVersion).where(
                    RobotVersion.robot_id == robot_id,
                    RobotVersion.is_active.is_(True),
                )
            )
        )
        assert len(active_versions) == 1
        assert active_versions[0].id == initial_version_id

    settings.artifacts_root = original_artifacts_root
