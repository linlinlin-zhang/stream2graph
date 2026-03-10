#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-$HOME/stream2graph_local}"
VENV_DIR="${1:-$LOCAL_RUN_ROOT/.venv-finetune}"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url https://download.pytorch.org/whl/cu124 torch torchvision torchaudio
python -m pip install -r "$ROOT_DIR/requirements/finetune.txt"

python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
    print("bf16_supported", torch.cuda.is_bf16_supported())
PY
