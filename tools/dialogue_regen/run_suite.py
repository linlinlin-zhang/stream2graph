#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import repo_root, resolve_path, utc_iso, write_json
from tools.eval.reporting import markdown_table


STEP_SCRIPTS = {
    "generation": "tools/dialogue_regen/run_generation.py",
    "metrics": "tools/dialogue_regen/run_metrics.py",
    "report": "tools/dialogue_regen/build_report.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a full dialogue regeneration suite.")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--python-executable", type=str, default=sys.executable)
    return parser.parse_args()


def _run_step(step_name: str, step_config: dict, python_executable: str, output_dir: Path) -> dict:
    config_dir = output_dir / "resolved_configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path = config_dir / f"{step_name}.json"
    write_json(resolved_config_path, step_config)

    script_path = repo_root() / STEP_SCRIPTS[step_name]
    command = [python_executable, str(script_path), "--config", str(resolved_config_path)]
    started = time.time()
    completed = subprocess.run(
        command,
        cwd=repo_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    duration = round(time.time() - started, 3)

    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{step_name}.stdout.log"
    stderr_path = log_dir / f"{step_name}.stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    return {
        "step": step_name,
        "config": str(resolved_config_path),
        "script": str(script_path),
        "command": command,
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "duration_seconds": duration,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }


def _manifest_markdown(manifest: dict) -> str:
    rows = [
        {
            "step": row["step"],
            "status": row["status"],
            "duration_seconds": row["duration_seconds"],
            "config": row["config"],
        }
        for row in manifest["steps"]
    ]
    parts = [
        f"# {manifest['title']}",
        "",
        f"- Generated at (UTC): {manifest['generated_at_utc']}",
        "",
        "## Steps",
        "",
        markdown_table(
            rows,
            [
                ("Step", "step"),
                ("Status", "status"),
                ("Duration Seconds", "duration_seconds"),
                ("Config", "config"),
            ],
        ) if rows else "_No steps executed._",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    payload = json.loads(resolve_path(args.config).read_text(encoding="utf-8"))
    output_dir = resolve_path(payload.get("output_dir", "reports/dialogue_regen/runs/suite"))
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at_utc": utc_iso(),
        "title": payload.get("title", "Dialogue Regeneration Suite"),
        "output_dir": str(output_dir),
        "python_executable": args.python_executable,
        "steps": [],
    }

    for step_name in ("generation", "metrics", "report"):
        step_config = payload.get("steps", {}).get(step_name)
        if not step_config:
            continue
        print(f"[dialogue-suite] running {step_name}", flush=True)
        result = _run_step(step_name, step_config, args.python_executable, output_dir)
        manifest["steps"].append(result)
        if result["status"] != "ok":
            write_json(output_dir / "suite_manifest.json", manifest)
            (output_dir / "suite_manifest.md").write_text(_manifest_markdown(manifest), encoding="utf-8")
            raise SystemExit(1)

    write_json(output_dir / "suite_manifest.json", manifest)
    (output_dir / "suite_manifest.md").write_text(_manifest_markdown(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()

