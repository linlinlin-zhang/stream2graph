#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import read_json, resolve_path
from tools.eval.reporting import markdown_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a markdown report for dialogue regeneration.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--summary-json", type=str, default="reports/dialogue_regen/runs/metrics/summary.json")
    parser.add_argument("--output-markdown", type=str, default="reports/dialogue_regen/runs/report.md")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**payload)
    return parser.parse_args()


def _metric_rows(summary: dict) -> list[dict]:
    rows: list[dict] = []
    for field, value in summary.get("overall", {}).items():
        if not value:
            continue
        row = {"metric": field}
        row.update(value)
        rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    summary = read_json(resolve_path(args.summary_json))
    output_markdown = resolve_path(args.output_markdown)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)

    overall_rows = _metric_rows(summary)
    diagram_rows = []
    for item in summary.get("by_diagram_type", []):
        metric = item.get("metrics", {}).get("proxy_quality_score") or {}
        diagram_rows.append(
            {
                "group": item.get("group"),
                "count": item.get("count"),
                "proxy_quality_mean": metric.get("mean"),
                "proxy_quality_p95": metric.get("p95"),
            }
        )
    bucket_rows = []
    for item in summary.get("by_reference_turn_bucket", []):
        metric = item.get("metrics", {}).get("proxy_quality_score") or {}
        bucket_rows.append(
            {
                "group": item.get("group"),
                "count": item.get("count"),
                "proxy_quality_mean": metric.get("mean"),
                "proxy_quality_p95": metric.get("p95"),
            }
        )
    failure_rows = [
        {
            "sample_id": row.get("sample_id"),
            "diagram_type": row.get("diagram_type"),
            "parse_valid": row.get("parse_valid"),
            "proxy_quality_score": row.get("proxy_quality_score"),
            "error": row.get("error"),
        }
        for row in summary.get("top_failures", [])
    ]

    parts = [
        "# Dialogue Regeneration Report",
        "",
        f"- Generated at (UTC): {summary.get('generated_at_utc')}",
        f"- Input predictions: `{summary.get('input_jsonl')}`",
        f"- Sample count: `{summary.get('sample_count')}`",
        f"- Providers: `{', '.join(summary.get('providers', []))}`",
        f"- Models: `{', '.join(summary.get('models', []))}`",
        "",
        "## Overall Metrics",
        "",
        markdown_table(
            overall_rows,
            [
                ("Metric", "metric"),
                ("Count", "count"),
                ("Mean", "mean"),
                ("P95", "p95"),
                ("Rate", "rate"),
            ],
        ) if overall_rows else "_No metrics._",
        "",
        "## By Diagram Type",
        "",
        markdown_table(
            diagram_rows,
            [
                ("Diagram Type", "group"),
                ("Count", "count"),
                ("Proxy Quality Mean", "proxy_quality_mean"),
                ("Proxy Quality P95", "proxy_quality_p95"),
            ],
        ) if diagram_rows else "_No rows._",
        "",
        "## By Reference Turn Bucket",
        "",
        markdown_table(
            bucket_rows,
            [
                ("Turn Bucket", "group"),
                ("Count", "count"),
                ("Proxy Quality Mean", "proxy_quality_mean"),
                ("Proxy Quality P95", "proxy_quality_p95"),
            ],
        ) if bucket_rows else "_No rows._",
        "",
        "## Lowest-Scoring Examples",
        "",
        markdown_table(
            failure_rows,
            [
                ("Sample ID", "sample_id"),
                ("Diagram Type", "diagram_type"),
                ("Parse Valid", "parse_valid"),
                ("Proxy Quality", "proxy_quality_score"),
                ("Error", "error"),
            ],
        ) if failure_rows else "_No failures._",
        "",
        "## Interpretation",
        "",
        "- These are proxy metrics, not a substitute for human judgement.",
        "- The current reference dialogues come from the earlier rule-based reverse engine, so role and action F1 should be treated as format alignment signals instead of gold semantic truth.",
        "- For model selection, prioritize parse validity, grounding recall, and low-error failure cases before looking at style.",
        "",
    ]
    output_markdown.write_text("\n".join(parts), encoding="utf-8")
    print(output_markdown)


if __name__ == "__main__":
    main()
