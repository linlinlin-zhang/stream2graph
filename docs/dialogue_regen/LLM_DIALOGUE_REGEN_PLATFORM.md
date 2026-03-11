# LLM Dialogue Regeneration Platform

This folder documents the platform under `tools/dialogue_regen/`.

## Goal

The goal is to replace the old rule-based reverse engine with a reproducible LLM-based
pipeline for `Mermaid code -> collaborative CSCW dialogue`.

The platform is designed for two phases:

1. Pilot selection
   - compare a small set of candidate LLMs on the same held-out slice
   - decide one primary generator model
2. Full regeneration
   - regenerate the training split with one primary model
   - keep validation and test frozen

## Why one primary model is better than mixing many models

For the final regenerated training corpus, a single primary model is usually better.

Reasons:

- the dialogue style stays consistent
- role balance and action rhythm stay more stable
- downstream SFT sees one annotation distribution instead of several competing ones
- failures are easier to trace back to one prompt or one model family

Recommended practice:

- use multiple models only in the pilot stage
- pick one primary generator for the full training split
- optionally use a second stronger model only as a repair or judge layer, not as a co-equal generator

## Initial pilot models

The repository currently materializes these first-pass candidates:

- `gpt-4.1`
  - strong non-reasoning structured generation
  - stable for JSON-only outputs
- `gemini-2.5-pro`
  - long-context, strong reasoning, can be forced into low-thinking mode for this task
- `deepseek-chat`
  - low-cost Chinese-capable baseline
- `qwen3-max`
  - strong Chinese commercial baseline through DashScope

This initial set is intentionally small. It is enough to answer:

- which model is the most parse-stable
- which model produces the best grounding
- which model gives the best quality/cost tradeoff

## Folder structure

- `tools/dialogue_regen/dataset.py`
  - loads held-out samples and renders the reverse-generation prompt
- `tools/dialogue_regen/parsing.py`
  - extracts and normalizes JSON dialogue outputs
- `tools/dialogue_regen/providers.py`
  - API backends for OpenAI Responses, Gemini, Anthropic, and OpenAI-compatible endpoints
- `tools/dialogue_regen/run_generation.py`
  - unified generation entrypoint
- `tools/dialogue_regen/metrics.py`
  - proxy quality metrics for generated dialogue
- `tools/dialogue_regen/run_metrics.py`
  - scores one run and emits summaries
- `tools/dialogue_regen/build_report.py`
  - writes the markdown report for one run
- `tools/dialogue_regen/run_suite.py`
  - orchestration entrypoint for one run
- `tools/dialogue_regen/materialize_pilot_matrix.py`
  - materializes the candidate pilot runs into per-model suite configs

## Core metrics

These are proxy metrics, not final human judgement:

- parse validity
- turn count match score against the existing reference dialogue
- valid role rate
- valid action rate
- alternation rate
- role coverage rate
- core action coverage rate
- grounding recall against Mermaid-derived code terms
- structured element precision
- role/action F1 against the old reference dialogue
- proxy quality score

Important:

- the old reference dialogue is still rule-generated
- therefore the role/action F1 numbers are format alignment signals, not gold semantic truth
- model selection should prioritize parse validity, grounding, and qualitative review of failure cases

## Recommended actual workflow

### 1. Materialize the pilot matrix

```bash
python tools/dialogue_regen/materialize_pilot_matrix.py --config configs/dialogue_regen/pilot_matrix_candidates_v1.example.json
```

### 2. Fill API keys

- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`

### 3. Execute the pilot matrix

```bash
python tools/dialogue_regen/materialize_pilot_matrix.py --config configs/dialogue_regen/pilot_matrix_candidates_v1.example.json --execute
```

### 4. Inspect reports

Each run writes:

- `reports/dialogue_regen/runs/<run_name>/generated.jsonl`
- `reports/dialogue_regen/runs/<run_name>/metrics/summary.json`
- `reports/dialogue_regen/runs/<run_name>/report.md`

### 5. Pick one primary model

After the pilot, choose one primary model for full train-split regeneration.

Recommended selection criteria:

1. parse validity
2. grounding recall
3. proxy quality score
4. manual spot-check quality on 30 to 50 examples
5. cost and latency

## Default dataset choice

For pilot comparison, use:

- source dataset: `release_v4_20260311`
- split: `validation`

For full regeneration, use:

- source dataset: `release_v4_20260311`
- split: `train`

Do not regenerate validation or test for the final paper benchmark.

