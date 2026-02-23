# Enesa Automation Hub - Backend

Backend corporativo em FastAPI, SQL Server e Redis para registry de robos e portal de autoatendimento.

## Stack

- FastAPI + Uvicorn
- SQL Server via SQLAlchemy + pyodbc
- Redis para fila de execucao e pub/sub de logs
- WebSocket para logs em tempo real
- Azure AD OIDC/JWKS + fallback local
- RBAC granular por permissao
- Metricas Prometheus em `/metrics`

## Setup

1. Copiar `.env.example` para `.env`.
2. Instalar dependencias: `pip install -r requirements.txt`.
3. Executar migracoes SQL:
   - `migrations/0001_initial_schema.sql`
   - `migrations/0002_enterprise_security_observability.sql`
   - `migrations/0003_robot_versions_registry.sql`
   - `migrations/0004_self_service_portal.sql`
4. Subir API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
5. Subir worker: `python -m app.workers.executor`.
6. Subir cleanup: `python -m app.workers.cleanup`.

## Endpoints

### Registry de robos

- `POST /api/v1/robots`
- `GET /api/v1/robots`
- `PATCH /api/v1/robots/{robot_id}/tags`
- `POST /api/v1/robots/{robot_id}/versions/publish`
- `GET /api/v1/robots/{robot_id}/versions`
- `POST /api/v1/robots/{robot_id}/versions/{version_id}/activate`

### Runs

- `POST /api/v1/runs/{robot_id}/execute`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/logs`
- `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download`
- `WS /api/v1/ws/runs/{run_id}/logs?token=<jwt>`

### Portal

- `POST/GET/PATCH/DELETE /api/v1/domains`
- `POST/GET/PATCH/DELETE /api/v1/services`
- `GET /api/v1/domains/{slug}/services`
- `POST /api/v1/services/{service_id}/run`
- `GET /api/v1/services/{service_id}/runs`

### Admin

- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}/permissions`
- `POST /api/v1/users/{user_id}/permissions`

## Portal JSON contracts

### form_schema_json

```json
{
  "fields": [
    {
      "key": "periodo",
      "label": "Periodo",
      "type": "text",
      "required": true,
      "default": "2026-02",
      "helpText": "YYYY-MM",
      "validation": {
        "regex": "^\\d{4}-\\d{2}$"
      }
    }
  ]
}
```

### run_template_json

```json
{
  "defaults": {
    "incluir_inativos": false
  },
  "mapping": {
    "runtime_arguments": [
      "--periodo={periodo}",
      "--inativos={incluir_inativos}"
    ],
    "runtime_env": {
      "SERVICE_DOMAIN": "dp-rh"
    }
  }
}
```

## RBAC

- `Viewer`: `service.read`, `robot.read`, `run.read`, `artifact.download`
- `Operator`: Viewer + `service.run`, `robot.run`
- `Maintainer`: Operator + `robot.publish`
- `Admin`: todas as permissoes, incluindo `service.manage` e `admin.manage`

## Testes

```bash
python -m pytest tests -q
```
