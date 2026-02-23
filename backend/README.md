# Enesa Automation Hub - Backend

Backend corporativo em FastAPI para registry de robos, scheduler, SLA monitor, deploy CI/CD e Config/Secrets.

## Stack

- FastAPI + Uvicorn
- SQL Server via SQLAlchemy + pyodbc
- Redis para fila e pub/sub de logs
- WebSocket para logs em tempo real
- Azure AD OIDC/JWKS + fallback local
- RBAC granular

## Setup

1. Copiar `.env.example` para `.env`
2. `pip install -r requirements.txt`
3. Executar migracoes SQL `0001` a `0007`
4. Subir API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
5. Subir processos:
   - `python -m app.workers.executor`
   - `python -m app.workers.cleanup`
   - `python -m app.workers.scheduler`
   - `python -m app.workers.sla_monitor`

## Endpoints

### Registry

- `POST /api/v1/robots/{robot_id}/versions/publish`
- `GET /api/v1/robots/{robot_id}/versions`
- `POST /api/v1/robots/{robot_id}/versions/{version_id}/activate`

### Deploy (GitHub Actions)

- `POST /api/v1/deploy/robots/{robot_id}/versions/publish`
  - Auth via `x-deploy-token`
  - Campos: `version`, `changelog`, `commit_sha`, `branch`, `build_url`, `activate`, `artifact`

### Config/Secrets

- `GET /api/v1/robots/{robot_id}/env?env=PROD|HML|TEST`
- `PUT /api/v1/robots/{robot_id}/env?env=PROD|HML|TEST`
- `DELETE /api/v1/robots/{robot_id}/env/{key}?env=PROD|HML|TEST`

### Scheduler

- `POST /api/v1/robots/{robot_id}/schedule`
- `GET /api/v1/robots/{robot_id}/schedule`
- `PATCH /api/v1/robots/{robot_id}/schedule`
- `DELETE /api/v1/robots/{robot_id}/schedule`

### SLA

- `POST /api/v1/robots/{robot_id}/sla`
- `GET /api/v1/robots/{robot_id}/sla`
- `PATCH /api/v1/robots/{robot_id}/sla`

### Alertas

- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{alert_id}/resolve`

## Scheduler rules

- Intervalo do scheduler: `SCHEDULER_INTERVAL_SECONDS` (default `30`)
- Timezone default: `America/Sao_Paulo`
- Lock de concorrencia por robo
- Timeout por run (`timeout_seconds`)
- Retry com backoff (`retry_count`, `retry_backoff_seconds`)

## SLA monitor rules

- Intervalo: `SLA_MONITOR_INTERVAL_SECONDS` (default `60`)
- Threshold de fila: `QUEUE_BACKLOG_ALERT_THRESHOLD`
- Worker stale threshold: `WORKER_STALE_SECONDS`
- Failure streak: `FAILURE_STREAK_THRESHOLD`

## Testes

```bash
python -m pytest tests -q
```
