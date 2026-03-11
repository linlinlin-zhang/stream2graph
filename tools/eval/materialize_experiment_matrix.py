#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import resolve_path, slugify, utc_iso, write_json
from tools.eval.reporting import markdown_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize or run a paper experiment matrix.")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--run", action="store_true", help="Run each experiment after materializing configs.")
    return parser.parse_args()


def _materialize_experiment(experiment: dict, matrix_root: Path) -> dict:
    experiment_id = slugify(str(experiment["id"]))
    experiment_dir = matrix_root / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    config_path = experiment_dir / "runner_config.json"
    runner_config = dict(experiment.get("config", {}))
    write_json(config_path, runner_config)
    return {
        "id": experiment_id,
        "title": str(experiment.get("title", experiment_id)),
        "group": str(experiment.get("group", "ungrouped")),
        "runner": str(experiment["runner"]),
        "config_path": str(config_path),
        "enabled": bool(experiment.get("enabled", True)),
    }


def _run_experiment(experiment_row: dict) -> int:
    command = [
        sys.executable,
        str(resolve_path(experiment_row["runner"])),
        "--config",
        experiment_row["config_path"],
    ]
    completed = subprocess.run(command, cwd=resolve_path("."), check=False)
    return completed.returncode


def main() -> None:
    args = parse_args()
    matrix_config = json.loads(resolve_path(args.config).read_text(encoding="utf-8"))
    matrix_name = str(matrix_config.get("name", "paper_experiment_matrix"))
    output_root = resolve_path(matrix_config.get("output_root", "reports/evaluation/matrix"))
    matrix_root = output_root / slugify(matrix_name)
    matrix_root.mkdir(parents=True, exist_ok=True)

    experiments = []
    for experiment in matrix_config.get("experiments", []):
        experiments.append(_materialize_experiment(experiment, matrix_root))

    execution_rows = []
    if args.run:
        for row in experiments:
            if not row["enabled"]:
                execution_rows.append({**row, "status": "skipped", "returncode": ""})
                continue
            returncode = _run_experiment(row)
            execution_rows.append(
                {
                    **row,
                    "status": "ok" if returncode == 0 else "failed",
                    "returncode": returncode,
                }
            )
    else:
        execution_rows = [
            {**row, "status": "materialized", "returncode": ""}
            for row in experiments
        ]

    manifest = {
        "generated_at_utc": utc_iso(),
        "matrix_name": matrix_name,
        "matrix_root": str(matrix_root),
        "config_path": str(resolve_path(args.config)),
        "experiments": execution_rows,
    }
    write_json(matrix_root / "matrix_manifest.json", manifest)

    rows = [
        {
            "id": row["id"],
            "group": row["group"],
            "runner": row["runner"],
            "status": row["status"],
            "config_path": row["config_path"],
        }
        for row in execution_rows
    ]
    markdown = "\n".join(
        [
            f"# {matrix_name}",
            "",
            f"- Generated at (UTC): {manifest['generated_at_utc']}",
            f"- Matrix root: {manifest['matrix_root']}",
            "",
            "## Experiments",
            "",
            markdown_table(
                rows,
                [
                    ("ID", "id"),
                    ("Group", "group"),
                    ("Runner", "runner"),
                    ("Status", "status"),
                    ("Config Path", "config_path"),
                ],
            ),
        ]
    ).strip() + "\n"
    (matrix_root / "matrix_manifest.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
