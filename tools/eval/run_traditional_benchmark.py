#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import resolve_path, slugify, write_json
from tools.eval.export_run_bundle import export_entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the heuristic / traditional Stream2Graph benchmark workflow.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--split", type=str, default="test", choices=["train", "validation", "test", "all"])
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--source-dir", type=str, default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_20260228")
    parser.add_argument("--split-dir", type=str, default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_20260228/splits")
    parser.add_argument("--turn-interval-ms", type=int, default=450)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--time-scale", type=float, default=1.0)
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--min-wait-k", type=int, default=1)
    parser.add_argument("--base-wait-k", type=int, default=2)
    parser.add_argument("--max-wait-k", type=int, default=4)
    parser.add_argument("--expected-intent-strategy", type=str, default="diagram_type_proxy", choices=["none", "diagram_type_proxy"])
    parser.add_argument("--intent-acc-threshold", type=float, default=0.0)
    parser.add_argument("--diagram-export-style", type=str, default="auto")
    parser.add_argument("--compile-command", type=str, default="")
    parser.add_argument("--run-name", type=str, default="")
    parser.add_argument("--output-root", type=str, default="reports/evaluation/runs/traditional")
    parser.add_argument("--publish-bundle", action="store_true")
    parser.add_argument("--published-dir", type=str, default="reports/evaluation/published")
    parser.add_argument("--notes", type=str, default="")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    return parser.parse_args()


def _run_script(script: str, config_path: Path) -> None:
    command = [sys.executable, str(resolve_path(script)), "--config", str(config_path)]
    subprocess.run(command, cwd=resolve_path("."), check=True)


def main() -> None:
    args = parse_args()
    run_name = args.run_name or slugify(f"traditional_{args.split}")
    run_root = resolve_path(args.output_root) / run_name
    config_root = run_root / "configs"
    inference_dir = run_root / "inference"
    offline_dir = run_root / "offline"
    realtime_dir = run_root / "realtime"
    report_dir = run_root / "report"
    config_root.mkdir(parents=True, exist_ok=True)

    inference_config = {
        "source_dir": args.source_dir,
        "split_dir": args.split_dir,
        "split": args.split,
        "max_samples": args.max_samples,
        "resume": True,
        "output_jsonl": str(inference_dir / "predictions.jsonl"),
        "manifest_output": str(inference_dir / "manifest.json"),
        "provider": "traditional_rule_based",
        "model": "traditional_rule_based",
        "turn_interval_ms": args.turn_interval_ms,
        "realtime": args.realtime,
        "time_scale": args.time_scale,
        "max_chunks": args.max_chunks,
        "min_wait_k": args.min_wait_k,
        "base_wait_k": args.base_wait_k,
        "max_wait_k": args.max_wait_k,
        "expected_intent_strategy": args.expected_intent_strategy,
        "diagram_export_style": args.diagram_export_style,
    }
    offline_config = {
        "input_jsonl": str(inference_dir / "predictions.jsonl"),
        "output_dir": str(offline_dir),
        "compile_command": args.compile_command,
    }
    realtime_config = {
        "source_dir": args.source_dir,
        "split_dir": args.split_dir,
        "split": args.split,
        "output_dir": str(realtime_dir),
        "max_samples": args.max_samples,
        "turn_interval_ms": args.turn_interval_ms,
        "realtime": args.realtime,
        "time_scale": args.time_scale,
        "max_chunks": args.max_chunks,
        "min_wait_k": args.min_wait_k,
        "base_wait_k": args.base_wait_k,
        "max_wait_k": args.max_wait_k,
        "expected_intent_strategy": args.expected_intent_strategy,
        "intent_acc_threshold": args.intent_acc_threshold,
    }
    report_config = {
        "title": "Traditional Heuristic Stream2Graph Benchmark",
        "offline_summary": str(offline_dir / "offline_metrics.summary.json"),
        "realtime_summary": str(realtime_dir / "realtime_metrics.summary.json"),
        "output_dir": str(report_dir),
        "notes": args.notes or "Traditional heuristic baseline benchmark for Stream2Graph.",
    }
    suite_config = {
        "title": "Traditional Heuristic Stream2Graph Evaluation Suite",
        "output_dir": str(run_root / "suite"),
        "stop_on_error": True,
        "steps": {
            "inference": {"enabled": True, "config": str(config_root / "inference.json")},
            "offline_metrics": {"enabled": True, "config": str(config_root / "offline_metrics.json")},
            "realtime_metrics": {"enabled": True, "config": str(config_root / "realtime_metrics.json")},
            "benchmark_report": {"enabled": True, "config": str(config_root / "benchmark_report.json")},
        },
    }

    inference_config_path = config_root / "inference.json"
    offline_config_path = config_root / "offline_metrics.json"
    realtime_config_path = config_root / "realtime_metrics.json"
    report_config_path = config_root / "benchmark_report.json"
    suite_config_path = config_root / "suite.json"
    write_json(inference_config_path, inference_config)
    write_json(offline_config_path, offline_config)
    write_json(realtime_config_path, realtime_config)
    write_json(report_config_path, report_config)
    write_json(suite_config_path, suite_config)

    _run_script("tools/eval/run_eval_suite.py", suite_config_path)

    if args.publish_bundle:
        bundle_dir = export_entries(
            bundle_name=run_name,
            published_dir=args.published_dir,
            entries=[
                ("configs", config_root),
                ("inference", inference_dir),
                ("offline", offline_dir),
                ("realtime", realtime_dir),
                ("report", report_dir),
                ("suite", run_root / "suite"),
            ],
            notes=args.notes or "Published traditional heuristic benchmark bundle.",
        )
        print(f"Published bundle: {bundle_dir}")

    print(f"Run root: {run_root}")


if __name__ == "__main__":
    main()
