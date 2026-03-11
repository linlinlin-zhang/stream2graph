#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.dialogue_regen.metrics import score_dialogue
from tools.eval.common import append_jsonl, read_jsonl, resolve_path, utc_iso, write_json
from tools.eval.reporting import (
    aggregate_rows,
    dialogue_turn_bucket,
    group_rows,
    top_failure_examples,
    write_csv,
)


METRIC_FIELDS = [
    "parse_valid",
    "generated_turns",
    "reference_turns",
    "turn_count_match_score",
    "nonempty_utterance_rate",
    "avg_utterance_chars",
    "valid_role_rate",
    "valid_action_rate",
    "alternation_rate",
    "role_coverage_rate",
    "core_action_coverage_rate",
    "execute_turn_ratio",
    "repair_turn_ratio",
    "grounding_recall",
    "structured_element_precision",
    "role_f1_vs_reference",
    "action_f1_vs_reference",
    "proxy_quality_score",
    "latency_ms",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score dialogue regeneration outputs.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--input-jsonl", type=str, default="reports/dialogue_regen/runs/generation.jsonl")
    parser.add_argument("--output-dir", type=str, default="reports/dialogue_regen/runs/metrics")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**payload)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_jsonl = resolve_path(args.input_jsonl)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(input_jsonl)
    scored_jsonl = output_dir / "scored_rows.jsonl"
    if scored_jsonl.exists():
        scored_jsonl.unlink()

    scored_rows: list[dict] = []
    for row in rows:
        source_path = Path(str(row["source_path"]))
        raw_sample = json.loads(source_path.read_text(encoding="utf-8"))
        generated_payload = row.get("generated_dialogue") or {}
        generated_turns = generated_payload.get("cscw_dialogue", []) if isinstance(generated_payload, dict) else []
        metrics = score_dialogue(
            reference_dialogue=raw_sample.get("cscw_dialogue", []),
            predicted_dialogue=generated_turns,
            code=str(raw_sample.get("code", "")),
        )
        scored = {
            "sample_id": row.get("sample_id"),
            "split": row.get("split"),
            "diagram_type": row.get("diagram_type"),
            "source_path": row.get("source_path"),
            "provider": row.get("provider"),
            "model_name": row.get("model_name"),
            "parse_valid": bool(row.get("parse_valid")),
            "parse_warning_count": len(row.get("parse_warnings", [])) if isinstance(row.get("parse_warnings"), list) else 0,
            "error": row.get("error"),
            "latency_ms": row.get("latency_ms"),
            **metrics,
        }
        scored["reference_turn_bucket"] = dialogue_turn_bucket(int(scored["reference_turns"]))
        append_jsonl(scored_jsonl, scored)
        scored_rows.append(scored)

    by_diagram_type = group_rows(scored_rows, "diagram_type", METRIC_FIELDS)
    by_reference_turn_bucket = group_rows(scored_rows, "reference_turn_bucket", METRIC_FIELDS)
    failures = top_failure_examples(scored_rows, "proxy_quality_score", limit=20)

    summary = {
        "generated_at_utc": utc_iso(),
        "input_jsonl": str(input_jsonl),
        "output_dir": str(output_dir),
        "sample_count": len(scored_rows),
        "metric_fields": METRIC_FIELDS,
        "overall": aggregate_rows(scored_rows, METRIC_FIELDS),
        "by_diagram_type": by_diagram_type,
        "by_reference_turn_bucket": by_reference_turn_bucket,
        "top_failures": failures,
        "providers": sorted({str(row.get("provider", "")) for row in scored_rows if row.get("provider")}),
        "models": sorted({str(row.get("model_name", "")) for row in scored_rows if row.get("model_name")}),
    }
    write_json(output_dir / "summary.json", summary)

    overview_row = {
        "sample_count": len(scored_rows),
        "providers": ", ".join(summary["providers"]),
        "models": ", ".join(summary["models"]),
    }
    for field in METRIC_FIELDS:
        field_summary = summary["overall"].get(field)
        if not field_summary:
            continue
        if "rate" in field_summary:
            overview_row[f"{field}_rate"] = field_summary["rate"]
        else:
            overview_row[f"{field}_mean"] = field_summary["mean"]
            overview_row[f"{field}_p95"] = field_summary["p95"]
    write_csv(output_dir / "overview.csv", [overview_row], list(overview_row.keys()))

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

