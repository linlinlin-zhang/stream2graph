#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-finetune}"
CONFIG_PATH="${ROOT_DIR}/configs/finetune/qwen3_14b_cloud_autodl.json"
LOG_DIR="${ROOT_DIR}/reports/finetune"
RUN_NAME="qwen3_14b_cloud_autodl"
LOG_FILE="${LOG_DIR}/${RUN_NAME}.log"
PID_FILE="${LOG_DIR}/${RUN_NAME}.pid"

mkdir -p "$LOG_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Missing virtual environment at $VENV_DIR"
  echo "Run tools/finetune/bootstrap_local_finetune_env.sh \"$VENV_DIR\" first."
  exit 1
fi

source "$VENV_DIR/bin/activate"

export HF_HOME="${HF_HOME:-/root/autodl-tmp/hf-cache}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

mkdir -p "$HF_HOME"
cd "$ROOT_DIR"

python "$ROOT_DIR/tools/finetune/prepare_qwen3_sft_dataset.py" \
  --output-dir "$ROOT_DIR/data/finetune/qwen3_release_sft_cloud"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Training process already running with PID $(cat "$PID_FILE")"
  exit 1
fi

nohup python -u "$ROOT_DIR/tools/finetune/train_qwen3_lora.py" \
  --config "$CONFIG_PATH" \
  > "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Started ${RUN_NAME} with PID $(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
