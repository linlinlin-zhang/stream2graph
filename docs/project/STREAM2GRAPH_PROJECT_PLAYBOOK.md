# Stream2Graph Project Playbook

This document consolidates the main technical and research decisions discussed for the
project up to `2026-03-11`. It is intended to be a working guide, not just a log.

## 1. Project snapshot

This repository is not only a dataset repo and not only a model repo. It currently
contains four connected layers:

- dataset engineering
- algorithm and realtime pipeline prototypes
- frontend and demo interface
- fine-tuning and evaluation tooling

The core repo areas are:

- `versions/`
  - historical and current research assets, especially the `v3` mainline
- `tools/`
  - repository-level scripts for release building, evaluation, serving, finetuning, and ops
- `frontend/`
  - the realtime UI demo
- `reports/`
  - runtime, release, and experiment outputs
- `docs/`
  - operations, training, workspace, and project planning notes

This project should be thought of as a full research system around realtime
dialogue-to-diagram generation.

## 2. Current dataset status

There are two important dataset views:

### 2.1 Internal mainline

- `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/cscw_dialogue_dataset`
- total samples: `9000`

This is the main internal training asset.

### 2.2 Current release subset

- `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_20260228`
- total samples: `4709`
- train split: `3759`
- validation split: `461`
- test split: `489`

This is the most practical dataset to use first for release-oriented training and paper
experiments.

## 3. Data complexity summary

The release subset is not trivial. It has a medium overall scale with a meaningful long tail.

### 3.1 Dialogue complexity

Measured on the `4709`-sample release subset:

- average dialogue turns: `16.35`
- p50 turns: `8`
- p90 turns: `38`
- p95 turns: `59`
- max turns: `120`

Approximate dialogue text length:

- average dialogue chars: `657.35`
- p90 dialogue chars: `1596`
- p95 dialogue chars: `2650`

### 3.2 Mermaid complexity

Measured on the same release subset:

- average Mermaid chars: `1238.89`
- p50 Mermaid chars: `817`
- p90 Mermaid chars: `2795`
- p95 Mermaid chars: `3755`
- max Mermaid chars: `9669`

Approximate non-empty code lines:

- average lines: `31.67`
- p50 lines: `22`
- p90 lines: `62`
- p95 lines: `93`
- max lines: `261`

Heuristic graph complexity signals:

- average edge-like links: `10.91`
- p90 edge-like links: `25`
- p95 edge-like links: `40`
- max edge-like links: `413`

- average unique node ids: `6.43`
- p90 unique node ids: `16`
- p95 unique node ids: `27`
- max unique node ids: `61`

### 3.3 Token length estimate

Using `Qwen3.5` tokenization on a random release-sample subset:

- average full sample length: about `845 tokens`
- p90 full sample length: about `1760 tokens`
- p95 full sample length: about `2431 tokens`
- over `1024` tokens: about `26.8%`
- over `1536` tokens: about `12.4%`
- over `2048` tokens: about `8.2%`

Implication:

- `1024` is a workable but lossy training context length
- `1536` is a strong practical compromise
- `2048` is better if hardware allows it

### 3.4 Diagram type distribution

Top types in the release subset:

- `stateDiagram`: `1027`
- `flowchart`: `622`
- `architecture`: `588`
- `gantt`: `569`
- `sequence`: `531`
- `gitGraph`: `321`
- `mindmap`: `236`
- `journey`: `214`

The dataset is structurally diverse enough to support a serious paper.

## 4. Model strategy

## 4.1 Main recommendation

Current recommended model plan:

- main model: `Qwen3.5-27B`
- fast baseline: `Qwen3.5-9B`
- optional comparison model: `Qwen3.5-35B-A3B`

This supersedes the older `Qwen2.5` shortlist for the mainline decision.

## 4.2 Why `Qwen3.5-27B`

For this project, the task is not simple classification. It is closer to:

- multi-turn dialogue understanding
- long-context instruction following
- structured code generation
- syntax-constrained Mermaid output

`Qwen3.5-27B` is currently the strongest first-choice open-weight student model for these
needs, balancing quality and practicality.

## 4.3 Why still keep `Qwen3.5-9B`

`Qwen3.5-9B` should still be trained because it is useful for:

- a cheaper fine-tuning baseline
- latency-oriented deployment experiments
- a possible fast path in a hybrid system
- a paper-scale comparison point

It should not replace `27B` as the main result model, but it is worth keeping.

## 4.4 What about `Qwen3.5-35B-A3B`

`Qwen3.5-35B-A3B` is a MoE model, not a configurable `27B` that can "activate only 9B".

Practical conclusion:

- it can be tested as a MoE comparison line
- it should not be the first mainline training target
- it is better treated as an optional architecture comparison or appendix result

If time is limited, prioritize `27B` and `9B` before MoE experiments.

## 4.5 Why `4-bit QLoRA`

For current hardware planning, `4-bit QLoRA` is the pragmatic training route because:

- it reduces memory pressure enough for single-GPU work
- it allows `27B`-class experimentation on rented hardware
- it is appropriate for medium-sized task adaptation

Important:

- the LoRA adapter is small and can be saved locally
- the full base model still has to be loaded on capable hardware for inference
- training and main evaluation should be done on cloud hardware, not on the local PC

## 5. Training and deployment workflow

## 5.1 Recommended training workflow

1. Rent a cloud GPU instance
2. Clone the repo to the fast local disk on the instance
3. Fine-tune on cloud
4. Run validation and test on cloud immediately after training
5. Save:
   - adapter checkpoints
   - configs
   - logs
   - metrics
   - predictions
6. Download these artifacts for archival

The main inference/deployment path should remain cloud-based for `27B`.

## 5.2 After fine-tuning

The typical artifact is not a full model dump. It is mainly:

- LoRA adapter
- config files
- tokenizer-related files
- metrics
- generated outputs

The adapter can be stored locally even if the full model cannot be run locally.

## 5.3 Practical usage after training

Recommended post-training setup:

- keep training and testing on cloud
- keep inference on cloud for the main model
- let the local machine handle only UI and development

If the system later needs a faster serving path, use:

- `9B` locally or on cheaper cloud
- `27B` on stronger cloud
- or a routed hybrid system

## 6. Experiment strategy

## 6.1 Main comparison groups considered

The discussions converged on four primary comparison categories:

1. partial-activation vs full-participation models
2. comparisons with general-purpose large models
3. comparisons with non-LLM traditional pipelines
4. same-model before-vs-after fine-tuning

## 6.2 Final priority recommendation

Even if all of them are possible, they do not have equal priority.

### Must-have

- same-model before vs after fine-tuning
- final system vs heuristic / traditional baseline
- small number of general-purpose model baselines

### Good to have

- one near-parameter open-weight baseline
- one strong closed-source API baseline

### Optional

- MoE vs dense architecture comparison

If resources are limited, architecture comparison should be the first thing to cut.

## 6.3 Best minimal experiment package

For a strong paper with manageable scope, the recommended minimum package is:

- `Qwen3.5-27B base` vs `Qwen3.5-27B + SFT`
- final system vs heuristic baseline
- final system vs one open-weight near-parameter model
- final system vs one strong closed-source API model
- one user study

Additional comparisons can be added only after these are solid.

## 7. Human study strategy

## 7.1 Do we need human evaluation?

For the current project direction, yes, ideally.

The offline metrics are necessary but not sufficient if the paper claims:

- the system helps real users
- the system improves diagramming workflow
- the system reduces effort or improves usability

Without human evidence, claims must stay narrower:

- better graph quality
- better compilation success
- better latency or stability

## 7.2 What the user study should test

The user study should compare systems, not every model.

Recommended system-level conditions:

1. manual baseline
2. heuristic / traditional system
3. final model-based system

Do not overload participants with every model variant.

## 7.3 Recommended participant count

For the first paper-quality study:

- `12-16` participants

Good participant pool:

- software engineers
- product managers
- researchers or students who do meeting synthesis
- users comfortable with structured documents or diagrams

## 7.4 Recommended study design

Use a within-subject design with counterbalancing.

Recommended task set:

- `6` tasks total
- `2` easy
- `2` medium
- `2` hard

Each task:

- uses held-out meeting/dialogue material
- asks the participant to produce or correct a Mermaid diagram

Per-session duration:

- about `60-75` minutes

## 7.5 What to record

Objective measures:

- task completion time
- edit count
- final diagram quality
- Mermaid compilation success
- first useful diagram latency
- number of accepted or rejected suggestions

Subjective measures:

- perceived usefulness
- perceived distraction
- trust
- workload
- usability

Qualitative materials:

- short interviews
- comments on failure cases
- ranking of system preferences

## 7.6 Statistics

Recommended basic analysis:

- paired non-parametric tests if sample size is small
- corrected multiple comparisons
- simple thematic analysis for interviews

The user study should be small but methodologically clean.

## 8. Conference strategy

## 8.1 Recommended target

Primary target recommendation:

- `ICMI 2026`

Reason:

- best fit for multimodal interactive systems and datasets
- more realistic schedule than `UIST 2026`
- better fit than `ASSETS 2026` unless the project is explicitly reframed around accessibility

## 8.2 Why not make `UIST 2026` the main target

`UIST` is a strong fit in spirit, but it demands:

- a more polished interaction story
- stronger HCI framing
- tighter timing

For the current schedule, it is riskier.

## 8.3 Why not make `ASSETS 2026` the main target

`ASSETS` would only become the best choice if the project is intentionally reframed as an
accessibility system and evaluated with representative users from the target population.

Without that accessibility-centered framing, it is not the first-choice venue.

## 8.4 What to optimize for if targeting ICMI

The paper should emphasize:

- multimodal or collaborative dialogue understanding
- dataset contribution
- realtime interactive system contribution
- careful but focused evaluation
- one solid user study

Do not turn the paper into a benchmark zoo.

## 9. Team fit and division of labor

Current assumed team structure:

- 2 people on technical work
- 2 people on user research
- 1 faculty advisor / corresponding author

This is a realistic and healthy team structure for an ICMI-style submission.

Suggested division:

- Technical lead A
  - training
  - inference
  - offline evaluation
- Technical lead B
  - realtime integration
  - logging
  - demo stability
- User research lead A
  - study design
  - task creation
  - questionnaires
- User research lead B
  - participant recruitment
  - study execution
  - qualitative coding
- Advisor
  - claim shaping
  - paper direction
  - methodology review

## 10. Recommended scope control

Even if there is enough time, not every experiment should receive the same amount of effort.

Recommended order of effort:

1. final main model and fine-tuning
2. before-vs-after comparison
3. traditional baseline comparison
4. one strong open or closed external baseline
5. user study
6. optional MoE vs dense comparison

If something has to be cut, cut model breadth before cutting user-study quality.

## 11. Immediate next steps

Recommended next actions in order:

1. freeze the conference target to `ICMI 2026`
2. freeze the main model to `Qwen3.5-27B`
3. keep `Qwen3.5-9B` as a secondary baseline
4. postpone `Qwen3.5-35B-A3B` unless extra time remains
5. finalize the evaluation protocol
6. finalize the user study protocol
7. train the first cloud model
8. run the minimum viable benchmark set
9. run the user study
10. write the paper around one clear claim

## 12. Main claim candidate

Strong current candidate:

`A fine-tuned dialogue-to-diagram model, coupled with a realtime incremental rendering pipeline, produces more accurate and more usable Mermaid diagrams from collaborative dialogue than prompting-only general models and heuristic baselines.`

This claim is tight enough to guide the experiments and broad enough to support an
ICMI-style story.
