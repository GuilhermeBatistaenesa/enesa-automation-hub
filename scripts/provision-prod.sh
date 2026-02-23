#!/usr/bin/env bash
set -euo pipefail

SKIP_START=0
REBUILD=0

for arg in "$@"; do
  case "$arg" in
    --skip-start) SKIP_START=1 ;;
    --rebuild) REBUILD=1 ;;
    *)
      echo "Opcao invalida: $arg"
      echo "Uso: ./scripts/provision-prod.sh [--skip-start] [--rebuild]"
      exit 1
      ;;
  esac
done

assert_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Comando '$cmd' nao encontrado no PATH."
    exit 1
  fi
}

ensure_file_from_template() {
  local template="$1"
  local target="$2"
  if [[ ! -f "$target" ]]; then
    cp "$template" "$target"
    echo "Arquivo criado: $target"
  else
    echo "Arquivo ja existe: $target"
  fi
}

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

assert_command docker

ensure_file_from_template "$INFRA_DIR/.env.prod.example" "$INFRA_DIR/.env.prod"
ensure_file_from_template "$BACKEND_DIR/.env.prod.example" "$BACKEND_DIR/.env"
ensure_file_from_template "$FRONTEND_DIR/.env.prod.example" "$FRONTEND_DIR/.env.local"

mkdir -p "$BACKEND_DIR/data/artifacts"

if [[ "$SKIP_START" -eq 0 ]]; then
  pushd "$INFRA_DIR" >/dev/null
  if [[ "$REBUILD" -eq 1 ]]; then
    docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
  else
    docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
  fi
  popd >/dev/null
fi

"$ROOT_DIR/scripts/verify-prod.sh"

echo "Provisionamento concluido."
