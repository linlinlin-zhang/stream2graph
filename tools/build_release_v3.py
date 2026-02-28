#!/usr/bin/env python3
"""
Build a cleaned, release-ready dataset from latest v3 snapshot.

Input:
  versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/cscw_dialogue_dataset

Output:
  versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_<date>
  reports/release_reports/release_v3_<timestamp>.{json,md}
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

INVALID_LICENSES = {"", "none", "error", "unknown", "rate_limited", None}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def detect_diagram_type_from_code(code: str) -> Optional[str]:
    c = code.lower()
    if "sequencediagram" in c:
        return "sequence"
    if "classdiagram" in c:
        return "class"
    if "erdiagram" in c:
        return "er"
    if "statediagram" in c:
        return "stateDiagram"
    if "gitgraph" in c:
        return "gitGraph"
    if "mindmap" in c:
        return "mindmap"
    if "journey" in c:
        return "journey"
    if "gantt" in c:
        return "gantt"
    if "pie" in c:
        return "pie"
    if "timeline" in c:
        return "timeline"
    if "xychart" in c:
        return "xychart"
    if "architecture" in c:
        return "architecture"
    if "flowchart" in c or "graph td" in c or "graph lr" in c:
        return "flowchart"
    if "c4context" in c:
        return "C4Context"
    if "requirementdiagram" in c:
        return "requirementDiagram"
    if "sankey" in c:
        return "sankey"
    if "packet-beta" in c:
        return "packet-beta"
    if "block-beta" in c:
        return "block-beta"
    if "kanban" in c:
        return "kanban"
    return None


def detect_diagram_type_from_id(sample_id: str) -> Optional[str]:
    sid = sample_id.lower()
    ordered = [
        ("requirementdiagram", "requirementDiagram"),
        ("statediagram", "stateDiagram"),
        ("gitgraph", "gitGraph"),
        ("c4context", "C4Context"),
        ("architecture", "architecture"),
        ("flowchart", "flowchart"),
        ("sequence", "sequence"),
        ("class", "class"),
        ("mindmap", "mindmap"),
        ("journey", "journey"),
        ("gantt", "gantt"),
        ("timeline", "timeline"),
        ("sankey", "sankey"),
        ("packet-beta", "packet-beta"),
        ("block-beta", "block-beta"),
        ("xychart", "xychart"),
        ("pie", "pie"),
        ("er", "er"),
        ("kanban", "kanban"),
    ]
    for key, value in ordered:
        if key in sid:
            return value
    return None


def infer_source(record: Dict, sample_id: str) -> Optional[str]:
    if record.get("source"):
        return str(record["source"])
    st = record.get("source_type")
    if st:
        return str(st)

    sid = sample_id.lower()
    if sid.startswith("aug_"):
        return "augmented_real_structure"
    if sid.startswith("gh_"):
        return "github"
    if sid.startswith("gl_"):
        return "gitlab"
    if sid.startswith("ot_"):
        return "other"
    return None


def normalize_license(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_record(
    filename: str,
    record: Dict,
    min_turns: int,
    max_turns: int,
) -> Tuple[Optional[Dict], List[str]]:
    reasons: List[str] = []

    sample_id = str(record.get("id") or Path(filename).stem)
    code = record.get("code")
    if not isinstance(code, str) or not code.strip():
        reasons.append("missing_code")

    comp = record.get("compilation_status")
    if comp != "success":
        reasons.append("compilation_not_success")

    license_key = normalize_license(record.get("license"))
    if license_key in INVALID_LICENSES:
        reasons.append("invalid_or_missing_license")

    dialogue = record.get("cscw_dialogue")
    if not isinstance(dialogue, list):
        reasons.append("missing_cscw_dialogue")
        turns = 0
    else:
        turns = len(dialogue)
        if turns < min_turns or turns > max_turns:
            reasons.append("dialogue_turns_out_of_range")

    diagram_type = record.get("diagram_type")
    if not diagram_type and isinstance(code, str):
        diagram_type = detect_diagram_type_from_code(code)
    if not diagram_type:
        diagram_type = detect_diagram_type_from_id(sample_id)
    if not diagram_type:
        reasons.append("missing_diagram_type")

    source = infer_source(record, sample_id)
    if not source:
        reasons.append("missing_source")

    if reasons:
        return None, reasons

    extra_keys = [
        "source_type",
        "source_url",
        "github_repo",
        "github_file_path",
        "repo",
        "seed_id",
        "augmentation_domain",
        "content_size",
        "collected_at",
        "license_name",
        "license_url",
        "repo_owner",
        "repo_name",
        "repo_stars",
        "repo_forks",
        "repo_topics",
        "repo_language",
        "repo_description",
        "repo_created_at",
        "repo_updated_at",
        "source_note",
    ]
    extra = {k: record[k] for k in extra_keys if k in record}

    normalized = {
        "id": sample_id,
        "source": source,
        "diagram_type": diagram_type,
        "code": code,
        "license": license_key,
        "compilation_status": "success",
        "cscw_dialogue": dialogue,
        "dialogue_metadata": record.get("dialogue_metadata", {"total_turns": turns}),
        "normalized_at": utc_now(),
        "extra": extra,
    }
    return normalized, []


def build_splits(ids: List[str], type_map: Dict[str, str], seed: int) -> Dict[str, List[str]]:
    rng = random.Random(seed)
    grouped: Dict[str, List[str]] = {}
    for sample_id in ids:
        grouped.setdefault(type_map[sample_id], []).append(sample_id)

    train: List[str] = []
    validation: List[str] = []
    test: List[str] = []

    for _, group_ids in grouped.items():
        rng.shuffle(group_ids)
        n = len(group_ids)
        n_train = int(n * 0.8)
        n_val = int(n * 0.1)
        n_test = n - n_train - n_val

        train.extend(group_ids[:n_train])
        validation.extend(group_ids[n_train : n_train + n_val])
        test.extend(group_ids[n_train + n_val : n_train + n_val + n_test])

    rng.shuffle(train)
    rng.shuffle(validation)
    rng.shuffle(test)

    return {"train": train, "validation": validation, "test": test}


def write_report_md(report: Dict, path: Path) -> None:
    lines: List[str] = []
    lines.append("# Release V3 Build Report")
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
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/cscw_dialogue_dataset",
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

    output_dir = output_root / f"release_v3_{date_tag}"
    ensure_dir(output_dir)

    reports_dir = Path("reports/release_reports")
    ensure_dir(reports_dir)

    files = sorted(source_dir.glob("*.json"))
    reason_counter: Counter = Counter()
    type_counter: Counter = Counter()
    source_counter: Counter = Counter()
    turns: List[int] = []
    type_map: Dict[str, str] = {}

    passed = 0
    for f in files:
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            reason_counter["invalid_json"] += 1
            continue

        normalized, reasons = normalize_record(f.name, record, args.min_turns, args.max_turns)
        if normalized is None:
            for reason in reasons:
                reason_counter[reason] += 1
            continue

        out_file = output_dir / f.name
        out_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

        passed += 1
        dtype = normalized["diagram_type"]
        src = normalized["source"]
        t = len(normalized["cscw_dialogue"])

        type_counter[dtype] += 1
        source_counter[src] += 1
        turns.append(t)
        type_map[normalized["id"]] = dtype

    ids = sorted(type_map.keys())
    splits = build_splits(ids, type_map, seed=args.seed)

    split_dir = output_dir / "splits"
    ensure_dir(split_dir)
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
            {"diagram_type": k, "count": v} for k, v in type_counter.most_common(20)
        ],
        "top_sources": [{"source": k, "count": v} for k, v in source_counter.most_common(20)],
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

    report_json = reports_dir / f"release_v3_{ts_tag}.json"
    report_md = reports_dir / f"release_v3_{ts_tag}.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report_md(report, report_md)

    latest_json = reports_dir / "release_v3_latest.json"
    latest_md = reports_dir / "release_v3_latest.md"
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_md.write_text(report_md.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
