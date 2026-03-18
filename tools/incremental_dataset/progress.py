from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.eval.common import read_json, utc_iso, write_json


ROLE_KEYS = ("stage_planner", "dialogue_writer", "turn_aligner", "verifier")


def inspect_agent_record(record: dict[str, Any]) -> dict[str, Any]:
    raw_status = str(record.get("status") or "missing")
    role_presence = {key: key in record for key in ROLE_KEYS}
    completed_roles = sum(1 for present in role_presence.values() if present)
    verifier = record.get("verifier") if isinstance(record.get("verifier"), dict) else {}
    has_verifier_result = isinstance(verifier, dict) and "result" in verifier
    has_final_dialogue = "final_dialogue" in record
    has_final_alignment = "final_alignment" in record
    has_top_level_error = bool(record.get("error"))
    has_warning = bool(record.get("warning"))

    if raw_status == "paused_for_quota":
        normalized_status = "paused_for_quota"
    elif has_final_dialogue and has_final_alignment:
        normalized_status = "completed" if has_verifier_result and not has_warning else "completed_with_warnings"
    elif completed_roles > 0:
        normalized_status = "partial_retry" if has_top_level_error or raw_status == "error" else "partial"
    elif has_top_level_error or raw_status == "error":
        normalized_status = "pending_retry"
    elif raw_status == "in_progress":
        normalized_status = "queued"
    else:
        normalized_status = "pending"

    return {
        "sample_id": record.get("sample_id"),
        "diagram_type": record.get("diagram_type", "unknown"),
        "raw_status": raw_status,
        "normalized_status": normalized_status,
        "role_presence": role_presence,
        "completed_role_count": completed_roles,
        "has_final_dialogue": has_final_dialogue,
        "has_final_alignment": has_final_alignment,
        "has_verifier_result": has_verifier_result,
        "has_top_level_error": has_top_level_error,
        "has_warning": has_warning,
        "is_finished": normalized_status in {"completed", "completed_with_warnings"},
        "is_unfinished": normalized_status not in {"completed", "completed_with_warnings"},
    }


def build_agent_progress_report(agent_dir: Path, include_examples: int = 5) -> dict[str, Any]:
    sample_paths = sorted(agent_dir.glob("*.json"))
    raw_status_counts: Counter[str] = Counter()
    normalized_status_counts: Counter[str] = Counter()
    role_progress_counts: Counter[str] = Counter()
    diagram_type_counts: Counter[str] = Counter()
    diagram_type_breakdown: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[str]] = defaultdict(list)

    for path in sample_paths:
        record = read_json(path)
        info = inspect_agent_record(record)
        raw_status_counts[info["raw_status"]] += 1
        normalized_status_counts[info["normalized_status"]] += 1
        role_progress_counts[str(info["completed_role_count"])] += 1
        diagram_type = str(info["diagram_type"])
        diagram_type_counts[diagram_type] += 1
        diagram_type_breakdown[diagram_type][info["normalized_status"]] += 1
        if len(examples[info["normalized_status"]]) < include_examples:
            examples[info["normalized_status"]].append(str(info["sample_id"]))

    completed_total = normalized_status_counts["completed"] + normalized_status_counts["completed_with_warnings"]
    unfinished_total = max(len(sample_paths) - completed_total, 0)
    completion_rate = round((completed_total / len(sample_paths)) * 100, 4) if sample_paths else 0.0

    return {
        "generated_at_utc": utc_iso(),
        "sample_output_dir": str(agent_dir),
        "total_samples": len(sample_paths),
        "completion": {
            "completed": normalized_status_counts["completed"],
            "completed_with_warnings": normalized_status_counts["completed_with_warnings"],
            "finished_total": completed_total,
            "unfinished_total": unfinished_total,
            "completion_rate_percent": completion_rate,
        },
        "normalized_status_counts": dict(normalized_status_counts),
        "raw_status_counts": dict(raw_status_counts),
        "role_progress_counts": dict(role_progress_counts),
        "diagram_type_counts": dict(diagram_type_counts),
        "diagram_type_breakdown": {
            diagram_type: dict(counts) for diagram_type, counts in sorted(diagram_type_breakdown.items())
        },
        "examples": dict(examples),
    }


def write_agent_progress_report(agent_dir: Path, output_path: Path) -> dict[str, Any]:
    payload = build_agent_progress_report(agent_dir)
    write_json(output_path, payload)
    return payload
