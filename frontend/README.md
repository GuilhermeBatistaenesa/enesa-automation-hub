# Enesa Automation Hub - Frontend

Interface corporativa em Next.js 14 (App Router) para operacao tecnica e autoatendimento por dominio.

## Paginas

- `/` Dashboard operacional
- `/robots` Cadastro e registry de versoes
- `/robots/[robotId]` Publish/rollback de versoes
- `/executions` Execucao remota manual por robo
- `/runs` Historico de runs e downloads
- `/portal` Lista de dominios do portal
- `/portal/[slug]` Catalogo de servicos por dominio
- `/portal/[slug]/[serviceId]` Formulario dinamico + execucao + terminal ao vivo
- `/admin/domains` CRUD de dominios
- `/admin/services` CRUD de servicos e editor JSON

## Setup

1. Copiar `.env.example` para `.env.local`
2. `npm install`
3. `npm run dev`

## Variaveis principais

- `NEXT_PUBLIC_API_BASE_URL` (ex: `http://localhost:8000/api/v1`)
- `NEXT_PUBLIC_WS_BASE_URL` (ex: `ws://localhost:8000/api/v1/ws`)
- `NEXT_PUBLIC_API_TOKEN` (token para ambiente interno)

## Notas

- Formularios do portal sao renderizados com base em `form_schema_json` enviado pelo backend.
- Execucao de servicos usa `POST /services/{service_id}/run` e stream via WebSocket em runs.
