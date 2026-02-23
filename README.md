# Enesa Automation Hub

Plataforma corporativa full-stack para cadastro de robos, execucao remota, portal por dominio e operacao automatica por scheduler/SLA.

## Arquitetura

- `backend/`: FastAPI + SQL Server + Redis + WebSocket
- `frontend/`: Next.js 14 (App Router)
- `backend/app/workers`: executor, cleanup, scheduler, sla_monitor

## Capacidades

- Registry de versoes com publish/rollback e SHA256
- Execucao manual e agendada (cron)
- Timeout por run, retry com backoff, lock de concorrencia
- SLA monitor com alertas: `LATE`, `FAILURE_STREAK`, `WORKER_DOWN`, `QUEUE_BACKLOG`
- Portal de autoatendimento com formularios dinamicos
- Controle operacional avancado: cancelamento de run, pause/resume de worker e painel operacional
- Deploy CI/CD estilo "Vercel interno" via GitHub Actions com `DEPLOY_TOKEN`
- Config/Secrets por robo e ambiente (`PROD`, `HML`, `TEST`) com criptografia em repouso
- RBAC, auditoria e metricas Prometheus

## Setup rapido

### Backend

1. `cd backend`
2. `pip install -r requirements.txt`
3. Configurar `.env`
4. Rodar migracoes SQL (`0001`..`0007`)
5. `uvicorn app.main:app --host 0.0.0.0 --port 8000`
6. `python -m app.workers.executor`
7. `python -m app.workers.cleanup`
8. `python -m app.workers.scheduler`
9. `python -m app.workers.sla_monitor`

### Frontend

1. `cd frontend`
2. `npm install`
3. Configurar `.env.local`
4. `npm run dev`

## Migracoes SQL Server

1. `backend/migrations/0001_initial_schema.sql`
2. `backend/migrations/0002_enterprise_security_observability.sql`
3. `backend/migrations/0003_robot_versions_registry.sql`
4. `backend/migrations/0004_self_service_portal.sql`
5. `backend/migrations/0005_scheduler_sla.sql`
6. `backend/migrations/0006_operational_control.sql`
7. `backend/migrations/0007_github_deploy_env_manager.sql`

## Endpoints principais

### Registry

- `POST /api/v1/robots/{robot_id}/versions/publish`
- `GET /api/v1/robots/{robot_id}/versions`
- `POST /api/v1/robots/{robot_id}/versions/{version_id}/activate`

### Scheduler + SLA + Alertas

- `POST /api/v1/robots/{robot_id}/schedule`
- `GET /api/v1/robots/{robot_id}/schedule`
- `PATCH /api/v1/robots/{robot_id}/schedule`
- `DELETE /api/v1/robots/{robot_id}/schedule`
- `POST /api/v1/robots/{robot_id}/sla`
- `GET /api/v1/robots/{robot_id}/sla`
- `PATCH /api/v1/robots/{robot_id}/sla`
- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{alert_id}/resolve`

### Operacoes

- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/workers`
- `POST /api/v1/workers/{worker_id}/pause`
- `POST /api/v1/workers/{worker_id}/resume`
- `GET /api/v1/ops/status`

### Deploy CI/CD + Config/Secrets

- `POST /api/v1/deploy/robots/{robot_id}/versions/publish` (via `x-deploy-token`)
- `GET /api/v1/robots/{robot_id}/env?env=PROD|HML|TEST`
- `PUT /api/v1/robots/{robot_id}/env?env=PROD|HML|TEST`
- `DELETE /api/v1/robots/{robot_id}/env/{key}?env=PROD|HML|TEST`

## GitHub Actions (exemplo)

```yaml
name: Publish Robot Version
on:
  workflow_dispatch:
    inputs:
      robot_id:
        required: true
      version:
        required: true

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build artifact
        run: |
          mkdir -p dist
          zip -r "dist/artifact.zip" . -x ".git/*"
      - name: Publish to Enesa Hub
        env:
          HUB_URL: ${{ secrets.ENESA_HUB_URL }}
          HUB_DEPLOY_TOKEN: ${{ secrets.ENESA_HUB_DEPLOY_TOKEN }}
        run: |
          curl -fSL -X POST \
            -H "x-deploy-token: ${HUB_DEPLOY_TOKEN}" \
            -F "version=${{ inputs.version }}" \
            -F "changelog=Published from GitHub Actions" \
            -F "commit_sha=${{ github.sha }}" \
            -F "branch=${{ github.ref_name }}" \
            -F "build_url=${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" \
            -F "activate=true" \
            -F "entrypoint_path=main.py" \
            -F "entrypoint_type=PYTHON" \
            -F "artifact=@dist/artifact.zip;type=application/zip" \
            "${HUB_URL}/api/v1/deploy/robots/${{ inputs.robot_id }}/versions/publish"
```

## Configurando criptografia de secrets

Gerar `ENCRYPTION_KEY` (Fernet):

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

### Runs

- `POST /api/v1/runs/{robot_id}/execute`
- `GET /api/v1/runs?trigger_type=MANUAL|SCHEDULED|RETRY`
- `GET /api/v1/runs/{run_id}/logs`
- `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download`

## Testes backend

```bash
cd backend
python -m pytest tests -q
```
