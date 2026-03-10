# Fine-Tune Model Shortlist

## Task Shape

Current `Stream2Graph` training samples are closer to `multi-turn dialogue -> structured Mermaid code`
than to a simple classifier:

- dialogue roles are mainly `Domain_Expert` and `Diagram_Editor`
- sampled dialogue length is about `16` turns on average, with a long tail to `30+`
- Mermaid code is about `1.3k` characters on average, with a long tail above `2.4k`
- the output must be syntactically valid and structurally stable

That makes model choice sensitive to:

- long-context quality
- code / structured-output reliability
- Chinese + English mixed dialogue tolerance
- fine-tuning cost small enough for iterative experiments

## Recommendation

### Tier 1: start here

1. `Qwen/Qwen2.5-14B-Instruct`
   - Best first model for this repo.
   - Reason: strong multilingual coverage, long context, and much lower tuning cost than 24B+ models.
   - Use it as the main supervised fine-tuning baseline for `dialogue -> full Mermaid`.

2. `Qwen/Qwen2.5-Coder-7B-Instruct`
   - Best cheap syntax-oriented baseline.
   - Reason: Mermaid is code-like output, so coder-tuned priors are useful for compilation rate and format control.
   - Use it for fast LoRA / QLoRA iteration and ablations.

### Tier 2: add after the first baseline is stable

3. `google/gemma-3-12b-it`
   - Best second-stage open-weight upgrade if we want stronger long-context instruction following without jumping to 24B.
   - Also keeps a path open for future multimodal extensions.

4. `mistralai/Mistral-Small-3.1-24B-Instruct-2503`
   - Best higher-capacity open-weight candidate for the same task once the data pipeline is stable.
   - Use it after we have a clean baseline and evaluation loop, because training cost is meaningfully higher.

### API route, not first local route

5. `gpt-4.1-mini-2025-04-14`
   - Good option if the goal is fastest quality validation through API fine-tuning instead of full local control.
   - I do not recommend it as the first path for this repo because the project still needs repeatable offline evaluation and dataset iteration.

## Why this order

### Primary path

`Qwen2.5-14B-Instruct` should be the first serious training run because it is the best balance of:

- multilingual robustness
- long-context support
- manageable tuning cost
- deployment practicality for a realtime system

### Fast baseline

`Qwen2.5-Coder-7B-Instruct` should run in parallel as the low-cost control model:

- cheaper to tune repeatedly
- likely strong on Mermaid syntax
- useful for deciding whether bigger models help semantics more than they help syntax

### Hold back the bigger model

`Mistral-Small-3.1-24B-Instruct-2503` is promising, but it should not be the first run because:

- the project still needs data conversion and evaluation hardening
- bigger models make debugging slower and more expensive
- we should first know whether failure is from data, prompting, or model capacity

## Not first-choice models

- `Meta-Llama-3.1-8B-Instruct`
  - Good baseline in general, but not my first pick here because the task appears to involve Chinese dialogue and Mermaid generation; Qwen is a better first fit.

- pure pretrained base checkpoints
  - Not recommended for the first phase.
  - For this project, instruction-tuned checkpoints are the pragmatic starting point; if needed, we can revisit raw base models after the first SFT baseline works.

## Immediate next step

Build the training stack around two first-pass models:

1. `Qwen/Qwen2.5-14B-Instruct`
2. `Qwen/Qwen2.5-Coder-7B-Instruct`

Everything else should be treated as follow-up comparison, not the initial implementation target.
