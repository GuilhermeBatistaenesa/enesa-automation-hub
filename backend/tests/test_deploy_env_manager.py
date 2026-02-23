from __future__ import annotations

import io
import uuid
import zipfile

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_principal
from app.api.v1.endpoints import deploy as deploy_endpoint
from app.api.v1.endpoints import robots as robots_endpoint
from app.core.config import get_settings
from app.core.rbac import PERMISSION_ROBOT_PUBLISH, PERMISSION_ROBOT_READ, Role
from app.db.base import Base
from app.db.session import get_db
from app.schemas.robot import RobotCreate, RobotVersionBase
from app.services.identity_service import Principal
from app.services.robot_service import create_robot


def _zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("main.py", "print('deploy test')\n")
        zipped.writestr("robot.yaml", "env:\n  required:\n    - API_TOKEN\n")
    return buffer.getvalue()


def test_deploy_publish_staged_and_env_secret_masking(tmp_path) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(robots_endpoint.router, prefix="/api/v1")
    app.include_router(deploy_endpoint.router, prefix="/api/v1")

    def override_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_principal() -> Principal:
        return Principal(
            subject="test-maintainer",
            auth_source="local",
            role=Role.MAINTAINER,
            permissions={PERMISSION_ROBOT_PUBLISH, PERMISSION_ROBOT_READ},
            user=None,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_principal] = override_principal

    settings = get_settings()
    original_artifacts_root = settings.artifacts_root
    original_deploy_token = settings.deploy_token
    original_encryption_key = settings.encryption_key
    settings.artifacts_root = tmp_path
    settings.deploy_token = "deploy-ci-token"
    settings.encryption_key = Fernet.generate_key().decode("utf-8")

    with testing_session_local() as db:
        robot = create_robot(
            db=db,
            created_by=None,
            payload=RobotCreate(
                name=f"robot-deploy-{uuid.uuid4()}",
                description="deploy test",
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
        robot_id = robot.id

    client = TestClient(app)

    deploy_response = client.post(
        f"/api/v1/deploy/robots/{robot_id}/versions/publish",
        headers={"x-deploy-token": settings.deploy_token},
        data={
            "version": "1.1.0",
            "changelog": "from github action",
            "commit_sha": "abc123def456",
            "branch": "main",
            "build_url": "https://github.com/enesa/repo/actions/runs/123",
            "activate": "false",
            "entrypoint_path": "main.py",
            "entrypoint_type": "PYTHON",
        },
        files={"artifact": ("artifact.zip", _zip_payload(), "application/zip")},
    )
    assert deploy_response.status_code == 201
    body = deploy_response.json()
    assert body["created_source"] == "github_actions"
    assert body["is_active"] is False
    assert body["commit_sha"] == "abc123def456"
    assert "API_TOKEN" in body["required_env_keys_json"]

    upsert_env_response = client.put(
        f"/api/v1/robots/{robot_id}/env?env=PROD",
        json={"items": [{"key": "API_TOKEN", "value": "super-secret-token", "is_secret": True}]},
    )
    assert upsert_env_response.status_code == 200

    list_env_response = client.get(f"/api/v1/robots/{robot_id}/env?env=PROD")
    assert list_env_response.status_code == 200
    listed = list_env_response.json()
    assert len(listed) == 1
    assert listed[0]["key"] == "API_TOKEN"
    assert listed[0]["is_secret"] is True
    assert listed[0]["is_set"] is True
    assert listed[0]["value"] is None

    settings.artifacts_root = original_artifacts_root
    settings.deploy_token = original_deploy_token
    settings.encryption_key = original_encryption_key
