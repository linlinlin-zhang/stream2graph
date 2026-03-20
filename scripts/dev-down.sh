#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/var/run"

stop_service() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not running"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    pkill -P "$pid" >/dev/null 2>&1 || true
    echo "Stopped $name (pid $pid)"
  else
    echo "$name pid file was stale"
  fi

  rm -f "$pid_file"
}

main() {
  stop_service "web" "$RUN_DIR/web.pid"
  stop_service "worker" "$RUN_DIR/worker.pid"
  stop_service "API" "$RUN_DIR/api.pid"

  if [[ "${S2G_STOP_DB:-0}" == "1" ]] && command -v docker >/dev/null 2>&1; then
    (cd "$ROOT_DIR" && docker compose -f docker-compose.platform.yml stop postgres)
    echo "Stopped PostgreSQL container"
  fi
}

main "$@"
