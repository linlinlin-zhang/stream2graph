#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="${ROOT_DIR}/reports/finetune/qwen3_14b_cloud_autodl.log"

tail -n 200 -f "$LOG_FILE"
