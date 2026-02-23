#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
ENV_FILE="$INFRA_DIR/.env.prod"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo infra/.env.prod nao encontrado."
  exit 1
fi

API_PORT=8000
FRONTEND_PORT=3000

while IFS= read -r line; do
  case "$line" in
    API_PORT=*) API_PORT="${line#API_PORT=}" ;;
    FRONTEND_PORT=*) FRONTEND_PORT="${line#FRONTEND_PORT=}" ;;
  esac
done < "$ENV_FILE"

echo "Verificando containers..."
pushd "$INFRA_DIR" >/dev/null
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
popd >/dev/null

echo "Verificando health endpoint da API..."
curl -fsS "http://localhost:${API_PORT}/api/v1/health" >/dev/null

echo "Verificando endpoint de metricas..."
curl -fsS "http://localhost:${API_PORT}/metrics" >/dev/null

echo "Verificando frontend..."
curl -fsS "http://localhost:${FRONTEND_PORT}" >/dev/null

echo "Verificacao concluida com sucesso."
