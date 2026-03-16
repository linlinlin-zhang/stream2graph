# Workspace Layout

## Core project areas

- `versions/`
  - Versioned dataset and algorithm snapshots. This is the historical core of the project.
- `tools/`
  - Active utility scripts.
  - `tools/finetune/` contains training-related scripts.
  - `tools/eval/` contains evaluation and benchmark scripts.
  - `tools/ops/` contains environment and runtime shell scripts.
- `frontend/`
  - Realtime UI.
- `configs/`
  - Runtime and training configuration files.
  - `configs/evaluation/` contains smoke, inference, traditional-baseline, shard, and paper-matrix configs.
  - `configs/evaluation/model_benchmarks/` contains the main large-model benchmark templates.
- `reports/`
  - Canonical reports that belong to the project workflow.
  - `reports/evaluation/runs/` is for generated benchmark outputs and should not be committed.
  - `reports/evaluation/published/` is for curated benchmark bundles that should be committed.
  - Evaluation run folders should prefer the normalized layout:
    - `configs/`
    - `inference/`
    - `offline/`
    - `realtime/` when applicable
    - `report/`
    - `suite/`
- `data/`
  - Active derived datasets that may still be reused.
  - `data/evaluation/` is reserved for generated benchmark fixtures.

## Documentation

- `README.md`
  - Project overview.
- `VERSION_INDEX.md`
  - Version-by-version dataset history.
- `docs/operations/`
  - Setup and runtime instructions.
- `docs/evaluation/`
  - Benchmark and scoring workflow documents.
- `docs/training/`
  - Fine-tuning notes and model selection documents.

## Archived non-core materials

- `workspace_archive/`
  - Temporary research extractions, local probe outputs, and other files that should be preserved but are not part of the active project flow.

## Placement rules

- New operational docs go in `docs/operations/`.
- New training docs go in `docs/training/`.
- New evaluation docs go in `docs/evaluation/`.
- New shell helpers for environment setup go in `tools/ops/`.
- New evaluation scripts go in `tools/eval/`.
- New paper experiment matrix templates go in `configs/evaluation/`.
- One-off probe outputs and temporary analysis artifacts should go to `workspace_archive/`, not the repository root.
- Generated runtime logs belong in `reports/runtime/`.
- Generated evaluation outputs belong in `reports/evaluation/runs/`, `artifacts/evaluation/`, or `data/evaluation/`.
- Commit-ready benchmark exports belong in `reports/evaluation/published/`.
- Flat launch logs under `reports/evaluation/runs/_launches/` should be treated carefully because some launch manifests store absolute paths to those files.
- If a provider folder accumulates loose one-off logs at its root, move them into a local `_orphan_logs/` subfolder instead of mixing them with normalized run directories.
