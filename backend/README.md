# Enesa Automation Hub - Backend

Backend corporativo em FastAPI, SQL Server e Redis para gestão e execução remota de robôs.

## Stack

- FastAPI + Uvicorn
- SQL Server via SQLAlchemy + pyodbc
- Redis para fila de execução e pub/sub de logs
- WebSocket para streaming de logs em tempo real

## Setup

1. Copiar `.env.example` para `.env`.
2. Instalar dependências:
   - `pip install -r requirements.txt`
3. Criar schema inicial:
   - Executar `migrations/0001_initial_schema.sql` no SQL Server
   - ou iniciar a API e deixar o bootstrap criar as tabelas.
4. Iniciar API:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
5. Iniciar worker:
   - `python -m app.workers.executor`

## Execução

- Endpoint para registrar robô: `POST /api/v1/robots`
- Endpoint para executar robô: `POST /api/v1/runs/{robot_id}/execute`
- Endpoint para consultar runs: `GET /api/v1/runs`
- WebSocket logs: `GET /api/v1/ws/runs/{run_id}/logs`

## Arquitetura

- `app/api`: camada HTTP e WebSocket
- `app/core`: config, segurança, autenticação
- `app/db`: sessão e bootstrap
- `app/models`: modelos SQLAlchemy
- `app/schemas`: contratos de entrada e saída
- `app/services`: regras de domínio e integrações
- `app/workers`: execução dos jobs em background
