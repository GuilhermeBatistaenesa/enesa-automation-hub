# Deploy de Producao - Enesa Automation Hub

## 1. Pre-requisitos

- Docker Engine + Docker Compose V2
- SQL Server e Redis acessiveis
- DNS interno e certificado TLS

## 2. Configuracao

Copiar templates:

- `infra/.env.prod.example` -> `infra/.env.prod`
- `backend/.env.prod.example` -> `backend/.env`
- `frontend/.env.prod.example` -> `frontend/.env.local`

## 3. Migracoes SQL

Executar em ordem:

1. `backend/migrations/0001_initial_schema.sql`
2. `backend/migrations/0002_enterprise_security_observability.sql`
3. `backend/migrations/0003_robot_versions_registry.sql`
4. `backend/migrations/0004_self_service_portal.sql`
5. `backend/migrations/0005_scheduler_sla.sql`
6. `backend/migrations/0006_operational_control.sql`
7. `backend/migrations/0007_github_deploy_env_manager.sql`

## 4. Processos obrigatorios

- API: `python -m app.main`
- Executor: `python -m app.workers.executor`
- Cleanup: `python -m app.workers.cleanup`
- Scheduler: `python -m app.workers.scheduler`
- SLA monitor: `python -m app.workers.sla_monitor`

Scripts prontos:

- `scripts/start-api.sh|ps1`
- `scripts/start-worker.sh|ps1`
- `scripts/start-cleanup.sh|ps1`
- `scripts/start-scheduler.sh|ps1`
- `scripts/start-sla-monitor.sh|ps1`

## 5. Reverse proxy, TLS e WebSocket

- Nginx: `infra/reverse-proxy/nginx/enesa-automation-hub.conf`
- IIS: `infra/reverse-proxy/iis/web.config`
- Confirmar WebSocket em `/api/v1/ws/*`

## 6. Variaveis importantes (scheduler/SLA)

- `APP_TIMEZONE=America/Sao_Paulo`
- `SCHEDULER_INTERVAL_SECONDS=30`
- `SLA_MONITOR_INTERVAL_SECONDS=60`
- `QUEUE_BACKLOG_ALERT_THRESHOLD=100`
- `WORKER_STALE_SECONDS=180`
- `FAILURE_STREAK_THRESHOLD=3`

## 7. Validacoes no servidor

1. Health `GET /api/v1/health`
2. Publish/activate de versao funcionando
3. Schedule criado e disparando run `trigger_type=SCHEDULED`
4. Retry criando `trigger_type=RETRY` com `attempt` crescente
5. Timeout gera `error_message=TIMEOUT`
6. SLA monitor gerando alertas em `GET /api/v1/alerts`
7. Resolucao de alerta em `POST /api/v1/alerts/{id}/resolve`
8. Dashboard exibindo cards de alertas/filas
9. Worker aparece em `GET /api/v1/workers` com heartbeat atualizado
10. Pause/Resume funcionando em `POST /api/v1/workers/{worker_id}/pause|resume`
11. Cancelamento de run em andamento funcionando em `POST /api/v1/runs/{run_id}/cancel`
12. Painel operacional `/admin/operations` exibindo fila, workers e runs em andamento
13. Deploy CI funcionando em `POST /api/v1/deploy/robots/{robot_id}/versions/publish` com `x-deploy-token`
14. Config/Secrets funcionando em `/api/v1/robots/{robot_id}/env?env=PROD`
15. Segredos nao aparecem em texto no GET e no frontend
16. Versoes exibindo metadados GitHub (`commit_sha`, `branch`, `build_url`)

## 8. Configuracao CI/CD e Secrets

- Definir `DEPLOY_TOKEN` no backend (diferente do token de login normal)
- Definir `ENCRYPTION_KEY` no backend (Fernet key)
- Criar secrets no GitHub:
  - `ENESA_HUB_URL`
  - `ENESA_HUB_DEPLOY_TOKEN`
- Garantir outbound HTTPS do runner ate o Hub interno
