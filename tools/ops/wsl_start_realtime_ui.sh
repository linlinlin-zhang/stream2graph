#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-wsl"
RUNTIME_DIR="${REPO_ROOT}/reports/runtime"

HOST="${1:-127.0.0.1}"
PORT="${2:-8088}"
PID_FILE="${RUNTIME_DIR}/realtime_ui_${PORT}.pid"
LOG_FILE="${RUNTIME_DIR}/realtime_ui_${PORT}.log"

mkdir -p "${RUNTIME_DIR}"
cd "${REPO_ROOT}"

if [[ -d "${VENV_DIR}" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  PYTHON_BIN="python"
else
  PYTHON_BIN="python3"
fi

if command -v ss >/dev/null 2>&1 && ss -ltn "( sport = :${PORT} )" | grep -q ":${PORT}"; then
  echo "Port ${PORT} is already in use." >&2
  exit 1
fi

nohup "${PYTHON_BIN}" tools/realtime_frontend_server.py --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
PID="$!"
echo "${PID}" > "${PID_FILE}"
sleep 2

if ! kill -0 "${PID}" >/dev/null 2>&1; then
  echo "Failed to start realtime UI server. See ${LOG_FILE}" >&2
  exit 1
fi

echo "Started Stream2Graph realtime UI."
echo "PID: ${PID}"
echo "URL: http://${HOST}:${PORT}"
echo "Log: ${LOG_FILE}"
