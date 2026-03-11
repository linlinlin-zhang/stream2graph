#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import repo_root, resolve_path, slugify, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize pilot dialogue-regeneration runs.")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--python-executable", type=str, default=sys.executable)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(resolve_path(args.config).read_text(encoding="utf-8"))
    base = payload.get("base", {})
    output_root = resolve_path(payload.get("output_dir", "artifacts/dialogue_regen/materialized/pilot"))
    output_root.mkdir(parents=True, exist_ok=True)

    materialized: list[str] = []
    for run in payload.get("runs", []):
        name = str(run["name"])
        slug = slugify(name)
        run_dir = output_root / slug
        run_dir.mkdir(parents=True, exist_ok=True)

        generation_output = f"reports/dialogue_regen/runs/{slug}/generated.jsonl"
        metrics_output_dir = f"reports/dialogue_regen/runs/{slug}/metrics"
        report_output = f"reports/dialogue_regen/runs/{slug}/report.md"
        suite_output_dir = f"reports/dialogue_regen/runs/{slug}/suite"

        suite_config = {
            "title": f"Dialogue regeneration pilot: {name}",
            "output_dir": suite_output_dir,
            "steps": {
                "generation": {
                    **base,
                    **run,
                    "output_jsonl": generation_output,
                },
                "metrics": {
                    "input_jsonl": generation_output,
                    "output_dir": metrics_output_dir,
                },
                "report": {
                    "summary_json": f"{metrics_output_dir}/summary.json",
                    "output_markdown": report_output,
                },
            },
        }
        config_path = run_dir / "suite.json"
        write_json(config_path, suite_config)
        materialized.append(str(config_path))

        if args.execute:
            subprocess.run(
                [args.python_executable, str(repo_root() / "tools/dialogue_regen/run_suite.py"), "--config", str(config_path)],
                cwd=repo_root(),
                check=False,
            )

    manifest = {
        "matrix_config": str(resolve_path(args.config)),
        "output_root": str(output_root),
        "materialized_runs": materialized,
    }
    write_json(output_root / "materialized_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

