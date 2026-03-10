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
  - `configs/evaluation/` contains benchmark and predictor config templates.
- `reports/`
  - Canonical reports that belong to the project workflow.
  - `reports/evaluation/` is for generated benchmark outputs and should not be committed.
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
- One-off probe outputs and temporary analysis artifacts should go to `workspace_archive/`, not the repository root.
- Generated runtime logs belong in `reports/runtime/`.
- Generated evaluation outputs belong in `reports/evaluation/`, `artifacts/evaluation/`, or `data/evaluation/`.
