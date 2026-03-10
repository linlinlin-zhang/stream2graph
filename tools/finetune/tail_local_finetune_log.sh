#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-$HOME/stream2graph_local}"
LOG_FILE="${LOCAL_RUN_ROOT}/logs/qwen3_14b_local_smoke.log"

tail -n 200 -f "$LOG_FILE"
