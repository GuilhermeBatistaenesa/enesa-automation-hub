# Deploy de Producao - Enesa Automation Hub

## 1. Pre-requisitos

- Docker Engine + Docker Compose V2
- DNS interno (ex: `automation-hub.enesa.local`)
- Certificado TLS no reverse proxy
- SQL Server e Redis acessiveis

## 2. Configuracoes

Copiar templates e preencher:

- `infra/.env.prod.example` -> `infra/.env.prod`
- `backend/.env.prod.example` -> `backend/.env`
- `frontend/.env.prod.example` -> `frontend/.env.local`

Campos criticos Azure AD:

- `AZURE_AD_TENANT_ID`
- `AZURE_AD_CLIENT_ID`
- `AZURE_AD_AUDIENCE`
- `AZURE_AD_GROUP_ADMIN_IDS`
- `AZURE_AD_GROUP_OPERATOR_IDS`
- `AZURE_AD_GROUP_VIEWER_IDS`

## 3. Provisionamento

### Linux

```bash
./scripts/provision-prod.sh --rebuild
```

### Windows

```powershell
.\scripts\provision-prod.ps1 -Rebuild
```

## 4. Migracoes SQL Server

Executar em ordem:

1. `backend/migrations/0001_initial_schema.sql`
2. `backend/migrations/0002_enterprise_security_observability.sql`
3. `backend/migrations/0003_robot_versions_registry.sql`
4. `backend/migrations/0004_self_service_portal.sql`

## 5. Reverse proxy + TLS + WebSocket

### Nginx

- Base: `infra/reverse-proxy/nginx/enesa-automation-hub.conf`
- Certificados:
  - `/etc/nginx/certs/automation-hub.crt`
  - `/etc/nginx/certs/automation-hub.key`
- Confirmar `location /api/v1/ws/` com upgrade WebSocket

### IIS

- Base: `infra/reverse-proxy/iis/web.config`
- Requer URL Rewrite + ARR + WebSocket Protocol
- Rota WebSocket: `api/v1/ws/*` para backend

## 6. Seguranca e acesso

- CORS restrito por `CORS_ORIGINS`
- Hosts permitidos por `ALLOWED_HOSTS`
- Headers de seguranca via middleware
- Auth:
  - local bootstrap (`/api/v1/auth/token`)
  - Azure AD OIDC/JWKS
- RBAC:
  - `service.read`, `service.run`, `service.manage`
  - `robot.read`, `robot.run`, `robot.publish`
  - `run.read`, `artifact.download`, `admin.manage`

## 7. Portal de autoatendimento

Tabelas:

- `domains`
- `services`
- `runs.service_id`
- `runs.parameters_json`

Fluxo:

1. Criar dominio (`DP/RH`)
2. Criar servico vinculando robo/versao
3. Definir `form_schema_json` e `run_template_json`
4. Usuario executa via `/portal`
5. Acompanhar logs/run/historico

## 8. Exemplo ASO/MetaX

### form_schema_json

```json
{
  "fields": [
    {
      "key": "periodo",
      "label": "Periodo (YYYY-MM)",
      "type": "text",
      "required": true,
      "validation": {
        "regex": "^\\d{4}-\\d{2}$"
      }
    },
    {
      "key": "origem",
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
  "mapping": {
    "runtime_arguments": [
      "--periodo={periodo}",
      "--origem={origem}"
    ],
    "runtime_env": {
      "SERVICE_AREA": "dp-rh"
    }
  }
}
```

## 9. Observabilidade

- Endpoint: `GET /metrics`
- Metricas:
  - `enesa_runs_total`
  - `enesa_runs_failed_total`
  - `enesa_run_duration_seconds`
  - `enesa_queue_depth`
  - `enesa_worker_heartbeat_unix`

## 10. Checklist de validacao (Servidor Enesa)

1. Containers `healthy` no compose
2. `GET /api/v1/health` com `200`
3. Home frontend carregando
4. WebSocket em `wss://.../api/v1/ws/runs/{run_id}/logs`
5. Token Azure AD aceito em `/api/v1/auth/me`
6. RBAC:
   - Viewer nao executa
   - Operator executa servicos
   - Admin cria/edita dominio e servico
7. Auditoria:
   - validar eventos `domain.*`, `service.*`, `service.run.triggered`
8. Registry:
   - publish/activate versao
   - run usando `version_id` correto
9. Portal:
   - dominio visivel em `/portal`
   - servico abre formulario dinamico
   - validacao de schema bloqueia parametros invalidos
10. Retencao e limpeza:
    - cleanup remove logs/artefatos antigos
11. Metricas disponiveis em `/metrics`

## 11. Operacao sem Docker

### Linux (systemd)

- `infra/systemd/enesa-api.service`
- `infra/systemd/enesa-worker.service`
- `infra/systemd/enesa-cleanup.service`
- `infra/systemd/enesa-frontend.service`

### Windows (NSSM)

- `infra/windows/install-services.ps1`
