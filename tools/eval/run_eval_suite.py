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
    "inference": "tools/eval/run_unified_inference.py",
    "offline_metrics": "tools/eval/run_offline_metrics.py",
    "realtime_metrics": "tools/eval/run_realtime_metrics.py",
    "benchmark_report": "tools/eval/build_benchmark_report.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a full Stream2Graph evaluation suite.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--title", type=str, default="Stream2Graph Evaluation Suite")
    parser.add_argument("--output-dir", type=str, default="reports/evaluation/suites/default_run")
    parser.add_argument("--python-executable", type=str, default=sys.executable)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--no-stop-on-error", action="store_true")
    parser.add_argument("--inference-config", type=str, default="")
    parser.add_argument("--offline-config", type=str, default="")
    parser.add_argument("--realtime-config", type=str, default="")
    parser.add_argument("--report-config", type=str, default="")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    args = parser.parse_args()
    if args.no_stop_on_error:
        args.stop_on_error = False
    elif not pre_args.config and not args.stop_on_error:
        args.stop_on_error = True
    return args


def _step_config_map(args: argparse.Namespace) -> dict[str, dict]:
    steps_from_config = getattr(args, "steps", None) or {}
    cli_fallback = {
        "inference": args.inference_config,
        "offline_metrics": args.offline_config,
        "realtime_metrics": args.realtime_config,
        "benchmark_report": args.report_config,
    }

    resolved: dict[str, dict] = {}
    for step_name in STEP_SCRIPTS:
        step_payload = dict(steps_from_config.get(step_name, {}))
        if "enabled" not in step_payload:
            step_payload["enabled"] = bool(step_payload.get("config") or cli_fallback[step_name])
        if not step_payload.get("config") and cli_fallback[step_name]:
            step_payload["config"] = cli_fallback[step_name]
        resolved[step_name] = step_payload
    return resolved


def _run_step(
    *,
    step_name: str,
    config_path: str,
    python_executable: str,
    output_dir: Path,
) -> dict:
    script_path = repo_root() / STEP_SCRIPTS[step_name]
    command = [python_executable, str(script_path), "--config", str(resolve_path(config_path))]
    started = time.time()
    started_iso = utc_iso()
    completed = subprocess.run(
        command,
        cwd=repo_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    duration = round(time.time() - started, 3)
    ended_iso = utc_iso()

    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{step_name}.stdout.log"
    stderr_path = log_dir / f"{step_name}.stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    return {
        "step": step_name,
        "script": str(script_path),
        "config": str(resolve_path(config_path)),
        "command": command,
        "started_at_utc": started_iso,
        "ended_at_utc": ended_iso,
        "duration_seconds": duration,
        "returncode": completed.returncode,
        "status": "ok" if completed.returncode == 0 else "failed",
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
        f"- Stop on error: {manifest['stop_on_error']}",
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
        )
        if rows
        else "_No steps executed._",
    ]
    failed = [row for row in manifest["steps"] if row["status"] != "ok"]
    if failed:
        parts.extend(["", "## Failures", ""])
        for row in failed:
            parts.append(
                f"- `{row['step']}` failed with return code `{row['returncode']}`. "
                f"See `{row['stderr_log']}`."
            )
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    steps = _step_config_map(args)
    manifest = {
        "generated_at_utc": utc_iso(),
        "title": args.title,
        "output_dir": str(output_dir),
        "python_executable": args.python_executable,
        "stop_on_error": bool(args.stop_on_error),
        "steps": [],
    }

    for step_name, step_payload in steps.items():
        if not step_payload.get("enabled"):
            continue
        config_path = step_payload.get("config")
        if not config_path:
            raise SystemExit(f"Step '{step_name}' is enabled but no config file was provided.")
        print(f"[suite] running {step_name} with {config_path}")
        step_result = _run_step(
            step_name=step_name,
            config_path=config_path,
            python_executable=args.python_executable,
            output_dir=output_dir,
        )
        manifest["steps"].append(step_result)
        if step_result["status"] != "ok":
            print(
                f"[suite] step {step_name} failed with return code {step_result['returncode']}.",
                file=sys.stderr,
            )
            if args.stop_on_error:
                break

    write_json(output_dir / "suite_manifest.json", manifest)
    (output_dir / "suite_manifest.md").write_text(_manifest_markdown(manifest), encoding="utf-8")

    failed_steps = [row for row in manifest["steps"] if row["status"] != "ok"]
    if failed_steps:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
