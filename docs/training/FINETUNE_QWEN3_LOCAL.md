# Local Qwen3 Fine-Tuning

This repo now includes a local QLoRA path for the first `Qwen3-14B` fine-tuning probe.

## What this run is

The default local run is intentionally conservative:

- base model: `unsloth/Qwen3-14B-unsloth-bnb-4bit`
- training method: QLoRA
- split source: `release_v3_20260228/splits`
- local subset: `512` train, `64` validation, `64` test
- max sequence length: `640`
- LoRA rank: `8`
- max steps: `200`

This is a local overnight probe, not the final cloud-scale training recipe.

## Files

- dataset prep: `tools/finetune/prepare_qwen3_sft_dataset.py`
- trainer: `tools/finetune/train_qwen3_lora.py`
- environment bootstrap: `tools/finetune/bootstrap_local_finetune_env.sh`
- local run entrypoint: `tools/finetune/run_local_qwen3_14b_smoke.sh`
- log tail helper: `tools/finetune/tail_local_finetune_log.sh`
- config: `configs/finetune/qwen3_14b_local_smoke.json`

## Start

```bash
cd /mnt/e/Desktop/stream2graph
bash tools/finetune/bootstrap_local_finetune_env.sh
bash tools/finetune/run_local_qwen3_14b_smoke.sh
```

By default the live run now stores heavy runtime files on the WSL local disk under
`$HOME/stream2graph_local/` to avoid slow cross-filesystem I/O from `/mnt/e`.
That includes the fine-tuning virtual environment.

## Monitor

```bash
cd /mnt/e/Desktop/stream2graph
bash tools/finetune/tail_local_finetune_log.sh
```

## Output

- logs: `$HOME/stream2graph_local/logs/`
- tensorboard: `$HOME/stream2graph_local/tensorboard/qwen3_14b_local_smoke`
- adapters and checkpoints: `$HOME/stream2graph_local/artifacts/qwen3_14b_local_smoke`
- prepared dataset: `$HOME/stream2graph_local/data/qwen3_release_sft_local_smoke`

## Notes

- The local run relies on CPU RAM and offloading to compensate for limited VRAM.
- If the local machine still runs out of memory, the same scripts can be moved to a rented GPU server without changing the data format.
