#!/usr/bin/env python3
"""
Build a strict V4 release dataset from the repaired 9k pool.

Rules:
- keep only records with compilation_status == success
- keep only records with a valid license
- keep only records with cscw_dialogue length in range
- write a fresh split directory and release report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_release_v3 import build_splits, ensure_dir, utc_now
from tools.repair_and_rebuild_v3 import INVALID_LICENSES, normalize_license


def valid_license(value: str | None) -> bool:
    return normalize_license(value) not in INVALID_LICENSES


def strict_keep(record: Dict, min_turns: int, max_turns: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if record.get("compilation_status") != "success":
        reasons.append("compilation_not_success")
    if not valid_license(record.get("license")):
        reasons.append("invalid_or_missing_license")
    dialogue = record.get("cscw_dialogue")
    if not isinstance(dialogue, list):
        reasons.append("missing_cscw_dialogue")
    else:
        turns = len(dialogue)
        if turns < min_turns or turns > max_turns:
            reasons.append("dialogue_turns_out_of_range")
    if not record.get("diagram_type"):
        reasons.append("missing_diagram_type")
    if not record.get("source"):
        reasons.append("missing_source")
    if not isinstance(record.get("code"), str) or not record.get("code", "").strip():
        reasons.append("missing_code")
    return (len(reasons) == 0), reasons


def write_report_md(report: Dict, path: Path) -> None:
    lines: List[str] = []
    lines.append("# Release V4 Build Report")
    lines.append("")
    lines.append(f"- Built at: {report['built_at_utc']}")
    lines.append(f"- Source directory: `{report['source_dir']}`")
    lines.append(f"- Output directory: `{report['output_dir']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Input files: {report['input_files']}")
    lines.append(f"- Passed records: {report['passed_records']}")
    lines.append(f"- Rejected records: {report['rejected_records']}")
    lines.append(f"- Pass rate: {report['pass_rate_percent']:.2f}%")
    lines.append("")
    lines.append("## Split Sizes")
    lines.append("")
    lines.append(f"- Train: {report['splits']['train']}")
    lines.append(f"- Validation: {report['splits']['validation']}")
    lines.append(f"- Test: {report['splits']['test']}")
    lines.append("")
    lines.append("## Rejection Reasons")
    lines.append("")
    for reason, count in report["rejection_reasons"].items():
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## Dialogue Turns")
    lines.append("")
    turns = report["dialogue_turns"]
    lines.append(f"- Min: {turns['min']}")
    lines.append(f"- Median: {turns['median']}")
    lines.append(f"- P95: {turns['p95']}")
    lines.append(f"- Max: {turns['max']}")
    lines.append("")
    lines.append("## Top Diagram Types")
    lines.append("")
    for item in report["top_diagram_types"]:
        lines.append(f"- {item['diagram_type']}: {item['count']}")
    lines.append("")
    lines.append("## Top Sources")
    lines.append("")
    for item in report["top_sources"]:
        lines.append(f"- {item['source']}: {item['count']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/compliant_v3_repaired_20260311",
    )
    parser.add_argument(
        "--output-root",
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset",
    )
    parser.add_argument("--min-turns", type=int, default=4)
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_root = Path(args.output_root)
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    output_dir = output_root / f"release_v4_{date_tag}"
    split_dir = output_dir / "splits"
    reports_dir = Path("reports/release_reports")
    ensure_dir(output_dir)
    ensure_dir(split_dir)
    ensure_dir(reports_dir)

    files = sorted(source_dir.glob("*.json"))
    reason_counter: Counter = Counter()
    type_counter: Counter = Counter()
    source_counter: Counter = Counter()
    turns: list[int] = []
    type_map: Dict[str, str] = {}

    passed = 0
    for file_path in files:
        try:
            record = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            reason_counter["invalid_json"] += 1
            continue

        keep, reasons = strict_keep(record, args.min_turns, args.max_turns)
        if not keep:
            for reason in reasons:
                reason_counter[reason] += 1
            continue

        normalized = dict(record)
        normalized["release_version"] = "v4"
        normalized["release_built_at"] = utc_now()
        normalized["license"] = normalize_license(record.get("license"))

        out_path = output_dir / file_path.name
        out_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

        passed += 1
        sample_id = str(normalized["id"])
        dtype = str(normalized["diagram_type"])
        src = str(normalized["source"])
        turn_count = len(normalized["cscw_dialogue"])
        turns.append(turn_count)
        type_map[sample_id] = dtype
        type_counter[dtype] += 1
        source_counter[src] += 1

    ids = sorted(type_map.keys())
    splits = build_splits(ids, type_map, seed=args.seed)
    for split_name, split_ids in splits.items():
        (split_dir / f"{split_name}_ids.json").write_text(
            json.dumps({"count": len(split_ids), "ids": split_ids}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if turns:
        turns_sorted = sorted(turns)
        t_min = turns_sorted[0]
        t_max = turns_sorted[-1]
        t_med = int(median(turns_sorted))
        t_p95 = turns_sorted[int(len(turns_sorted) * 0.95)]
    else:
        t_min = t_max = t_med = t_p95 = 0

    report = {
        "built_at_utc": utc_now(),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "input_files": len(files),
        "passed_records": passed,
        "rejected_records": len(files) - passed,
        "pass_rate_percent": (passed / len(files) * 100.0) if files else 0.0,
        "rejection_reasons": dict(reason_counter.most_common()),
        "dialogue_turns": {
            "min": t_min,
            "median": t_med,
            "p95": t_p95,
            "max": t_max,
        },
        "top_diagram_types": [
            {"diagram_type": key, "count": value}
            for key, value in type_counter.most_common(20)
        ],
        "top_sources": [
            {"source": key, "count": value}
            for key, value in source_counter.most_common(20)
        ],
        "splits": {
            "train": len(splits["train"]),
            "validation": len(splits["validation"]),
            "test": len(splits["test"]),
        },
        "config": {
            "min_turns": args.min_turns,
            "max_turns": args.max_turns,
            "seed": args.seed,
        },
    }

    report_json = reports_dir / f"release_v4_{ts_tag}.json"
    report_md = reports_dir / f"release_v4_{ts_tag}.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report_md(report, report_md)

    latest_json = reports_dir / "release_v4_latest.json"
    latest_md = reports_dir / "release_v4_latest.md"
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_md.write_text(report_md.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
