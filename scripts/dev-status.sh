#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/var/run"

print_service_status() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    printf "%-8s %s\n" "$name" "stopped"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    printf "%-8s %s\n" "$name" "running (pid $pid)"
  else
    printf "%-8s %s\n" "$name" "stale pid file"
  fi
}

main() {
  print_service_status "api" "$RUN_DIR/api.pid"
  print_service_status "worker" "$RUN_DIR/worker.pid"
  print_service_status "web" "$RUN_DIR/web.pid"

  if lsof -iTCP:5432 -sTCP:LISTEN >/dev/null 2>&1; then
    printf "%-8s %s\n" "postgres" "listening on 5432"
  else
    printf "%-8s %s\n" "postgres" "not listening on 5432"
  fi
}

main "$@"
