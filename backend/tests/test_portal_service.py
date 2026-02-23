from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_principal
from app.api.v1.endpoints import portal as portal_endpoint
from app.core.rbac import ALL_PERMISSIONS, Role
from app.db.base import Base
from app.db.session import get_db
from app.schemas.robot import RobotCreate, RobotVersionBase
from app.services import run_service
from app.services.identity_service import Principal
from app.services.robot_service import create_robot


def test_portal_domain_service_run_flow() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(portal_endpoint.router, prefix="/api/v1")

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_principal() -> Principal:
        return Principal(
            subject="portal-admin",
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
                name="portal-robot",
                description="Robot bound to service",
                tags=["rh"],
                initial_version=RobotVersionBase(
                    version="1.0.0",
                    channel="stable",
                    artifact_type="ZIP",
                    artifact_path="robots/portal-robot/1.0.0/artifact.zip",
                    artifact_sha256="sha-portal",
                    changelog="initial",
                    entrypoint_type="PYTHON",
                    entrypoint_path="main.py",
                    arguments=[],
                    env_vars={},
                    working_directory=None,
                    checksum="sha-portal",
                ),
            ),
        )
        robot_id = robot.id
        version_id = robot.versions[0].id

    queued_payloads: list[dict] = []

    async def fake_enqueue(payload: dict) -> None:
        queued_payloads.append(payload)

    original_enqueue = run_service.enqueue_run
    run_service.enqueue_run = fake_enqueue
    try:
        client = TestClient(app)

        create_domain = client.post(
            "/api/v1/domains",
            json={
                "name": "DP/RH",
                "slug": "dp-rh",
                "description": "Servicos para pessoal e RH",
            },
        )
        assert create_domain.status_code == 201
        domain_id = create_domain.json()["id"]

        create_service_resp = client.post(
            "/api/v1/services",
            json={
                "domain_id": domain_id,
                "robot_id": str(robot_id),
                "title": "Gerar relatorio ASO",
                "description": "Executa consolidacao de ASO",
                "icon": "file-text",
                "enabled": True,
                "default_version_id": str(version_id),
                "form_schema_json": {
                    "fields": [
                        {
                            "key": "periodo",
                            "label": "Periodo",
                            "type": "text",
                            "required": True,
                            "validation": {"regex": r"^\d{4}-\d{2}$"},
                        },
                        {
                            "key": "incluir_inativos",
                            "label": "Incluir Inativos",
                            "type": "checkbox",
                            "default": False,
                        },
                    ]
                },
                "run_template_json": {
                    "defaults": {"incluir_inativos": False},
                    "mapping": {
                        "runtime_arguments": ["--periodo={periodo}", "--inativos={incluir_inativos}"],
                        "runtime_env": {"SERVICE_DOMAIN": "dp-rh"},
                    },
                },
            },
        )
        assert create_service_resp.status_code == 201
        service_id = create_service_resp.json()["id"]

        list_domain_services = client.get("/api/v1/domains/dp-rh/services")
        assert list_domain_services.status_code == 200
        assert len(list_domain_services.json()) == 1

        invalid_run_resp = client.post(
            f"/api/v1/services/{service_id}/run",
            json={"parameters": {}},
        )
        assert invalid_run_resp.status_code == 400

        run_resp = client.post(
            f"/api/v1/services/{service_id}/run",
            json={"parameters": {"periodo": "2026-02"}},
        )
        assert run_resp.status_code == 202
        run_payload = run_resp.json()
        assert run_payload["service_id"] == service_id
        assert run_payload["parameters_json"]["periodo"] == "2026-02"
        assert len(queued_payloads) == 1
        assert queued_payloads[0]["runtime_arguments"] == ["--periodo=2026-02", "--inativos=false"]

        service_runs = client.get(f"/api/v1/services/{service_id}/runs")
        assert service_runs.status_code == 200
        assert len(service_runs.json()) == 1
    finally:
        run_service.enqueue_run = original_enqueue
