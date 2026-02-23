# Enesa Automation Hub

Plataforma corporativa full-stack para cadastro de robos, execucao remota e portal de autoatendimento por dominio.

## Arquitetura

- `backend/`: FastAPI + SQL Server + Redis + WebSocket de logs
- `frontend/`: Next.js 14 (App Router) com dashboard, registry de versoes e portal de servicos
- `infra/`: compose, reverse proxy (Nginx/IIS), scripts de operacao
- `backend/app/workers`: worker de execucao para scripts Python e binarios EXE

## Capacidades

- Registry de robos com versoes (SemVer), publish/rollback e artefatos versionados
- Execucao remota com fila Redis e stream de logs via WebSocket
- Historico de runs com download de artefatos e metadados
- Portal de autoatendimento por dominios (ex: DP/RH, Engenharia)
- Servicos com formulario dinamico (`form_schema_json`) e template de run (`run_template_json`)
- RBAC com papeis `Admin`, `Maintainer`, `Operator`, `Viewer`
- SSO Azure AD (OIDC/JWKS) com fallback local opcional
- Auditoria (`audit_events`) e metricas Prometheus (`/metrics`)

## Estrutura

```text
enesa-automation-hub/
|- backend/
|  |- app/
|  |- migrations/
|  |- tests/
|- frontend/
|  |- app/
|  |- components/
|  |- lib/
|- infra/
|- scripts/
```

## Setup rapido

### Backend

1. `cd backend`
2. `pip install -r requirements.txt`
3. Configurar `.env`
4. Rodar migracoes SQL (`0001`..`0004`)
5. Iniciar API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
6. Iniciar worker: `python -m app.workers.executor`
7. Iniciar cleanup: `python -m app.workers.cleanup`

### Frontend

1. `cd frontend`
2. `npm install`
3. Configurar `.env.local`
4. `npm run dev`

## Migracoes SQL Server

Executar em ordem:

1. `backend/migrations/0001_initial_schema.sql`
2. `backend/migrations/0002_enterprise_security_observability.sql`
3. `backend/migrations/0003_robot_versions_registry.sql`
4. `backend/migrations/0004_self_service_portal.sql`

## Principais tabelas

- `robots`, `robot_versions`, `robot_release_tags`
- `domains`, `services`
- `runs`, `run_logs`, `artifacts`
- `users`, `permissions`, `audit_events`

## Endpoints principais

### Registry de versoes

- `POST /api/v1/robots`
- `POST /api/v1/robots/{robot_id}/versions/publish`
- `GET /api/v1/robots/{robot_id}/versions`
- `POST /api/v1/robots/{robot_id}/versions/{version_id}/activate`

### Execucao

- `POST /api/v1/runs/{robot_id}/execute`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}/logs`
- `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download`
- `WS /api/v1/ws/runs/{run_id}/logs?token=<jwt>`

### Portal de autoatendimento

- `POST/GET/PATCH/DELETE /api/v1/domains`
- `POST/GET/PATCH/DELETE /api/v1/services`
- `GET /api/v1/domains/{slug}/services`
- `POST /api/v1/services/{service_id}/run`
- `GET /api/v1/services/{service_id}/runs`

## Fluxo do Portal

1. Admin cria dominio (ex: `DP/RH`).
2. Admin cria servico vinculando `robot_id` e opcional `default_version_id`.
3. Admin define `form_schema_json` e `run_template_json`.
4. Usuario do portal abre o servico, preenche formulario e executa.
5. Backend valida parametros, aplica template e cria run na fila Redis.
6. Usuario acompanha logs ao vivo e baixa artefatos no historico.

## Exemplo ASO/MetaX

### form_schema_json

```json
{
  "fields": [
    {
      "key": "periodo",
      "label": "Periodo (YYYY-MM)",
      "type": "text",
      "required": true,
      "helpText": "Exemplo: 2026-02",
      "validation": {
        "regex": "^\\d{4}-\\d{2}$"
      }
    },
    {
      "key": "incluir_inativos",
      "label": "Incluir colaboradores inativos",
      "type": "checkbox",
      "default": false
    },
    {
      "key": "sistema_origem",
      "label": "Sistema origem",
      "type": "select",
      "required": true,
      "options": [
        { "label": "ASO", "value": "aso" },
        { "label": "MetaX", "value": "metax" }
      ]
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
      "--inativos={incluir_inativos}",
      "--origem={sistema_origem}"
    ],
    "runtime_env": {
      "SERVICE_AREA": "dp-rh"
    }
  }
}
```

## RBAC

- `service.read`: visualizar portal
- `service.run`: executar servicos
- `service.manage`: criar/editar dominios e servicos
- `robot.read`, `robot.run`, `robot.publish`, `run.read`, `artifact.download`, `admin.manage`

## Testes backend

No diretório `backend/`:

```bash
python -m pytest tests -q
```
