#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "versions" / "v3_2026-02-27_latest_9k_cscw" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asr_stream_adapter import ASRChunk  # noqa: E402
from evaluate_realtime_pipeline import evaluate_payload  # noqa: E402
from run_realtime_pipeline import run_realtime_pipeline  # noqa: E402
from streaming_intent_engine import EngineConfig  # noqa: E402
from tools.eval.common import resolve_path, utc_iso, write_json  # noqa: E402
from tools.eval.dataset import DEFAULT_SOURCE_DIR, DEFAULT_SPLIT_DIR, load_evaluation_samples, sample_to_transcript_rows  # noqa: E402
from tools.eval.reporting import aggregate_rows, dialogue_turn_bucket, group_rows, markdown_table, top_failure_examples, write_csv  # noqa: E402
from tools.eval.traditional_baselines import proxy_intent_for_diagram_type  # noqa: E402


REALTIME_METRIC_FIELDS = [
    "realtime_eval_pass",
    "e2e_latency_p95_ms",
    "flicker_mean",
    "mental_map_mean",
    "runtime_over_transcript_ratio",
    "updates_emitted",
    "intent_accuracy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realtime benchmark runner for Stream2Graph.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--source-dir", type=str, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--split-dir", type=str, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--split", type=str, default="test", choices=["train", "validation", "test", "all"])
    parser.add_argument("--output-dir", type=str, default="reports/evaluation/realtime/default_run")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--sample-ids-file", type=str, default="")
    parser.add_argument("--turn-interval-ms", type=int, default=450)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--time-scale", type=float, default=1.0)
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--min-wait-k", type=int, default=1)
    parser.add_argument("--base-wait-k", type=int, default=2)
    parser.add_argument("--max-wait-k", type=int, default=4)
    parser.add_argument("--expected-intent-strategy", type=str, default="none", choices=["none", "diagram_type_proxy"])
    parser.add_argument("--latency-p95-threshold-ms", type=float, default=2000.0)
    parser.add_argument("--flicker-mean-threshold", type=float, default=6.0)
    parser.add_argument("--mental-map-min", type=float, default=0.85)
    parser.add_argument("--intent-acc-threshold", type=float, default=0.8)

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    return parser.parse_args()


def _load_sample_ids(path_value: str) -> set[str]:
    if not path_value:
        return set()
    path = resolve_path(path_value)
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("ids", payload) if isinstance(payload, dict) else payload
        return {str(item) for item in values}
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _realtime_row(sample, pipeline: dict, evaluation: dict) -> dict:
    metrics = evaluation.get("metrics", {})
    return {
        "sample_id": sample.sample_id,
        "split": sample.split,
        "diagram_type": sample.diagram_type,
        "dialogue_turns": sample.dialogue_turns,
        "dialogue_turn_bucket": dialogue_turn_bucket(sample.dialogue_turns),
        "realtime_eval_pass": evaluation.get("realtime_eval_pass"),
        "e2e_latency_p95_ms": metrics.get("e2e_latency_p95_ms"),
        "flicker_mean": metrics.get("flicker_mean"),
        "mental_map_mean": metrics.get("mental_map_mean"),
        "intent_accuracy": metrics.get("intent_accuracy"),
        "runtime_over_transcript_ratio": metrics.get("runtime_over_transcript_ratio"),
        "updates_emitted": metrics.get("updates_emitted"),
        "pipeline_mode": metrics.get("mode"),
        "runtime_ms": metrics.get("runtime_ms"),
        "transcript_duration_ms": metrics.get("transcript_duration_ms"),
        "threshold_checks": evaluation.get("checks", {}),
        "pipeline_summary": pipeline.get("summary", {}),
    }


def _summary_markdown(summary: dict) -> str:
    overall_rows = []
    overall = summary["overall"]
    for field in REALTIME_METRIC_FIELDS:
        metric = overall.get(field)
        if metric is None:
            continue
        overall_rows.append(
            {
                "metric": field,
                "count": metric.get("count"),
                "mean_or_rate": metric.get("mean", metric.get("rate")),
                "p50": metric.get("p50", ""),
                "p95": metric.get("p95", ""),
            }
        )

    by_type_rows = []
    for item in summary["slices"]["by_diagram_type"][:12]:
        by_type_rows.append(
            {
                "diagram_type": item["group"],
                "count": item["count"],
                "pass_rate": (item["metrics"].get("realtime_eval_pass") or {}).get("rate"),
                "latency_p95": (item["metrics"].get("e2e_latency_p95_ms") or {}).get("mean"),
                "flicker_mean": (item["metrics"].get("flicker_mean") or {}).get("mean"),
            }
        )

    parts = [
        "# Realtime Metrics Summary",
        "",
        f"- Generated at (UTC): {summary['generated_at_utc']}",
        f"- Sample count: {summary['sample_count']}",
        "",
        "## Overall",
        "",
        markdown_table(
            overall_rows,
            [
                ("Metric", "metric"),
                ("Count", "count"),
                ("Mean/Rate", "mean_or_rate"),
                ("P50", "p50"),
                ("P95", "p95"),
            ],
        ),
        "## By Diagram Type",
        "",
        markdown_table(
            by_type_rows,
            [
                ("Diagram Type", "diagram_type"),
                ("Count", "count"),
                ("Pass Rate", "pass_rate"),
                ("Latency P95", "latency_p95"),
                ("Flicker Mean", "flicker_mean"),
            ],
        ),
    ]
    return "\n".join(parts).strip() + "\n"


def main() -> None:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sample_ids = _load_sample_ids(args.sample_ids_file)
    samples = load_evaluation_samples(
        source_dir=args.source_dir,
        split_dir=args.split_dir,
        split=args.split,
        max_samples=args.max_samples,
        sample_ids=sample_ids if sample_ids else None,
    )

    config = EngineConfig(
        min_wait_k=args.min_wait_k,
        base_wait_k=args.base_wait_k,
        max_wait_k=args.max_wait_k,
    )

    detail_rows: list[dict] = []
    for sample in samples:
        transcript_rows = sample_to_transcript_rows(
            sample,
            interval_ms=args.turn_interval_ms,
            expected_intent_map=None,
        )
        if args.expected_intent_strategy == "diagram_type_proxy":
            proxy_intent = proxy_intent_for_diagram_type(sample.diagram_type)
            for row in transcript_rows:
                action_type = str(row.get("metadata", {}).get("action_type", ""))
                if action_type in {"propose", "clarify", "execute", "repair"}:
                    row["expected_intent"] = proxy_intent
                else:
                    row["expected_intent"] = None
        chunks = [
            ASRChunk(
                timestamp_ms=int(row["timestamp_ms"]),
                text=str(row["text"]),
                speaker=str(row.get("speaker", "user")),
                is_final=bool(row.get("is_final", True)),
                expected_intent=row.get("expected_intent"),
                metadata=row.get("metadata", {}),
            )
            for row in transcript_rows
        ]
        pipeline = run_realtime_pipeline(
            chunks=chunks,
            realtime=args.realtime,
            time_scale=args.time_scale,
            max_chunks=args.max_chunks,
            config=config,
        )
        evaluation = evaluate_payload(
            payload=pipeline,
            latency_p95_threshold_ms=args.latency_p95_threshold_ms,
            flicker_mean_threshold=args.flicker_mean_threshold,
            mental_map_min=args.mental_map_min,
            intent_acc_threshold=args.intent_acc_threshold,
        )
        row = _realtime_row(sample, pipeline, evaluation)
        detail_rows.append(row)
        print(
            f"[eval-realtime] sample={sample.sample_id} split={sample.split} "
            f"pass={row['realtime_eval_pass']} latency_p95={row['e2e_latency_p95_ms']}",
            flush=True,
        )

    summary = {
        "generated_at_utc": utc_iso(),
        "sample_count": len(detail_rows),
        "thresholds": {
            "latency_p95_threshold_ms": args.latency_p95_threshold_ms,
            "flicker_mean_threshold": args.flicker_mean_threshold,
            "mental_map_min": args.mental_map_min,
            "intent_acc_threshold": args.intent_acc_threshold,
            "expected_intent_strategy": args.expected_intent_strategy,
        },
        "overall": aggregate_rows(detail_rows, REALTIME_METRIC_FIELDS),
        "slices": {
            "by_diagram_type": group_rows(detail_rows, "diagram_type", REALTIME_METRIC_FIELDS),
            "by_dialogue_turn_bucket": group_rows(detail_rows, "dialogue_turn_bucket", REALTIME_METRIC_FIELDS),
        },
        "failure_examples": top_failure_examples(detail_rows, "mental_map_mean", limit=20),
    }

    detail_path = output_dir / "realtime_metrics.detail.jsonl"
    summary_path = output_dir / "realtime_metrics.summary.json"
    markdown_path = output_dir / "realtime_metrics.summary.md"
    csv_path = output_dir / "realtime_metrics.detail.csv"

    with detail_path.open("w", encoding="utf-8") as handle:
        for row in detail_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_json(summary_path, summary)
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")
    write_csv(
        csv_path,
        detail_rows,
        [
            "sample_id",
            "split",
            "diagram_type",
            "dialogue_turns",
            "dialogue_turn_bucket",
            "realtime_eval_pass",
            "e2e_latency_p95_ms",
            "flicker_mean",
            "mental_map_mean",
            "intent_accuracy",
            "runtime_over_transcript_ratio",
            "updates_emitted",
        ],
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
