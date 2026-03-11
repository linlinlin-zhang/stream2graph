# Paper Experiment Matrix

This document defines the intended paper-facing experiment groups for Stream2Graph.

## Main groups

1. Same-model before / after fine-tuning
   - Example: `Qwen3.5-27B base` vs `Qwen3.5-27B + SFT`
2. Traditional / heuristic baseline
   - The existing realtime intent engine plus incremental renderer
3. Frontier API baselines
   - Example: `GPT-4.1`, `Gemini 2.5 Pro`
4. Official OpenAI-compatible API baselines
   - Example: `DeepSeek`, `Kimi`, `Qwen DashScope`
5. Hosted open-weight baselines
   - Example: `SiliconFlow`-hosted Qwen models

## Available matrix configs

- `configs/evaluation/paper_matrix_icmi_smoke.json`
  - small materialization-only smoke matrix
- `configs/evaluation/paper_matrix_icmi_main.example.json`
  - main ICMI-oriented comparison matrix template
- `configs/evaluation/local_hf_qwen35_27b_base_benchmark.example.json`
  - dedicated local-HF base-model benchmark template
- `configs/evaluation/local_hf_qwen35_27b_sft_benchmark.example.json`
  - dedicated local-HF SFT benchmark template

## Matrix workflow

Materialize configs only:

```bash
python tools/eval/materialize_experiment_matrix.py --config configs/evaluation/paper_matrix_icmi_smoke.json
```

Materialize and run enabled experiments:

```bash
python tools/eval/materialize_experiment_matrix.py --config configs/evaluation/paper_matrix_icmi_smoke.json --run
```

## Current recommendation for ICMI

The default main matrix keeps the following priorities:

- include one traditional heuristic baseline
- include same-model before / after fine-tuning
- include one strong frontier API baseline
- include one or more official external API baselines
- defer very broad model sweeps unless there is spare time

## Notes on rigor

- Traditional baseline realtime `intent_accuracy` currently supports a `diagram_type_proxy`
  label strategy for diagnostics only.
- Paper claims should rely primarily on:
  - offline graph quality
  - compile success
  - realtime latency / flicker / mental-map stability
  - user study outcomes
- Proxy intent labels should not be reported as gold-standard intent annotations.
