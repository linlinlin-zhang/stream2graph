#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/reports/runtime"

PORT="${1:-8088}"
PID_FILE="${RUNTIME_DIR}/realtime_ui_${PORT}.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No pid file for port ${PORT}."
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" >/dev/null 2>&1; then
  kill "${PID}"
fi

rm -f "${PID_FILE}"
echo "Stopped realtime UI on port ${PORT}."
