# AutoDL Cloud Training

This document describes the shortest path to run the project on an AutoDL instance for `Qwen3-14B` fine-tuning.

## 1. Instance choices

- GPU: `1 x RTX 5090 32GB`
- Billing: start with pay-as-you-go for environment bring-up
- Data disk: `100GB`
- Image: `Miniconda / Python 3.10`

## 2. Login and create a persistent shell

```bash
ssh root@<your-host> -p <your-port>
tmux new -s stream2graph
```

## 3. Put the repository on the local training disk

Use the AutoDL local data disk path:

```bash
cd /root/autodl-tmp
git clone https://github.com/linlinlin-zhang/stream2graph.git
cd stream2graph
```

## 4. Optional but recommended: log in to Hugging Face

```bash
export HF_TOKEN=<your_hf_token>
huggingface-cli login --token "$HF_TOKEN"
```

## 5. Build the fine-tuning environment

```bash
cd /root/autodl-tmp/stream2graph
bash tools/finetune/bootstrap_local_finetune_env.sh /root/autodl-tmp/stream2graph/.venv-finetune
```

## 6. Start the cloud run

```bash
cd /root/autodl-tmp/stream2graph
bash tools/finetune/run_cloud_qwen3_14b_autodl.sh
```

This will:

- prepare `data/finetune/qwen3_release_sft_cloud`
- start the training process in the background
- write logs to `reports/finetune/qwen3_14b_cloud_autodl.log`

## 7. Monitor

```bash
cd /root/autodl-tmp/stream2graph
bash tools/finetune/tail_cloud_qwen3_14b_autodl_log.sh
```

## 8. Re-attach after disconnect

```bash
tmux attach -t stream2graph
```

## 9. Outputs

- logs: `reports/finetune/`
- checkpoints and adapters: `artifacts/finetune/qwen3_14b_cloud_autodl`
- prepared dataset: `data/finetune/qwen3_release_sft_cloud`

## 10. Stop the run manually

```bash
kill "$(cat reports/finetune/qwen3_14b_cloud_autodl.pid)"
```

## Notes

- Put the repository under `/root/autodl-tmp`, not under slower persistent storage paths.
- The cloud config lives in `configs/finetune/qwen3_14b_cloud_autodl.json`.
- The local bootstrap script is reused on cloud; the only difference is that the repository itself should be cloned onto the cloud instance's local disk.
