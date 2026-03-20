#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import read_json, resolve_path, utc_iso, write_json
from tools.eval.incremental_dataset import DEFAULT_INCREMENTAL_RUN_ROOT, load_incremental_entries
from tools.incremental_system.loader import load_runtime_sample


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive a clean incremental dataset run root from the frozen v1 benchmark."
    )
    parser.add_argument("--source-run-root", type=str, default=DEFAULT_INCREMENTAL_RUN_ROOT)
    parser.add_argument(
        "--output-run-root",
        type=str,
        default="data/incremental_dataset/runs/minimax_m27_incremental_full_v1_clean",
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default="reports/evaluation/published/incremental_dataset_full_v1_clean_analysis",
    )
    return parser.parse_args()


def _boundary_exact(sample) -> bool:
    turns = sorted(sample.turns, key=lambda item: item.turn_id)
    ordered_turn_ids = [int(turn.turn_id) for turn in turns]
    covered: list[int] = []
    last_end: int | None = None
    for boundary in sorted(sample.stage_boundaries, key=lambda item: item.stage_index):
        start_turn = int(boundary.start_turn)
        end_turn = int(boundary.end_turn)
        if end_turn < start_turn:
            return False
        if last_end is not None and start_turn != (last_end + 1):
            return False
        covered.extend(range(start_turn, end_turn + 1))
        last_end = end_turn
    return covered == ordered_turn_ids


def _sample_issues(sample) -> list[str]:
    turn_ids = [int(turn.turn_id) for turn in sample.turns]
    issues: list[str] = []
    if len(sample.stage_boundaries) != len(sample.stages):
        issues.append("boundary_count_mismatch")
    if not _boundary_exact(sample):
        issues.append("boundary_not_exact")
    if len(turn_ids) != len(set(turn_ids)):
        issues.append("duplicate_turn_ids")
    return issues


def _safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _link_dir(source: Path, target: Path) -> None:
    _safe_remove(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    os.symlink(source, target, target_is_directory=True)


def main() -> None:
    args = parse_args()
    source_root = resolve_path(args.source_run_root)
    output_root = resolve_path(args.output_run_root)
    report_output = resolve_path(args.report_output)

    entries = load_incremental_entries(source_root, split="all")
    bad_ids: set[str] = set()
    issue_counter: Counter[str] = Counter()
    diagram_removed_counter: Counter[str] = Counter()
    split_removed_counter: Counter[str] = Counter()
    issue_examples: list[dict[str, Any]] = []

    for entry in entries:
        sample = load_runtime_sample(source_root, entry.sample_id)
        issues = _sample_issues(sample)
        if not issues:
            continue
        bad_ids.add(entry.sample_id)
        for issue in issues:
            issue_counter[issue] += 1
        diagram_removed_counter[entry.diagram_type] += 1
        split_removed_counter[entry.split] += 1
        if len(issue_examples) < 20:
            issue_examples.append(
                {
                    "sample_id": entry.sample_id,
                    "split": entry.split,
                    "diagram_type": entry.diagram_type,
                    "issues": issues,
                }
            )

    clean_entries = [entry for entry in entries if entry.sample_id not in bad_ids]
    clean_ids = {entry.sample_id for entry in clean_entries}

    source_selection = source_root / "selection"
    selection_manifest = read_json(source_selection / "selection_manifest.json")
    filtered_profiles = [
        row
        for row in selection_manifest.get("selected_profiles", [])
        if str(row.get("sample_id", "")) in clean_ids
    ]
    selection_stats: dict[str, dict[str, Any]] = {}
    selected_counter = Counter(str(row.get("diagram_type", "unknown")) for row in filtered_profiles)
    for diagram_type, stats in (selection_manifest.get("selection_stats") or {}).items():
        selection_stats[diagram_type] = {
            **stats,
            "selected": int(selected_counter.get(diagram_type, 0)),
        }

    split_ids: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for entry in clean_entries:
        split_ids[entry.split].append(entry.sample_id)

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    _link_dir(source_root / "structure", output_root / "structure")
    _link_dir(source_root / "agent_cluster", output_root / "agent_cluster")

    selection_output = output_root / "selection"
    selection_output.mkdir(parents=True, exist_ok=True)
    for file_name in ("all_profiles.jsonl", "all_profiles.with_bucket.jsonl"):
        source_file = source_selection / file_name
        if source_file.exists():
            shutil.copy2(source_file, selection_output / file_name)

    write_json(selection_output / "selected_sample_ids.json", {"ids": sorted(clean_ids)})
    split_dir = selection_output / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    for split_name, ids in split_ids.items():
        write_json(split_dir / f"{split_name}_ids.json", {"ids": ids})

    clean_manifest = {
        "target_samples": len(clean_entries),
        "selected_count": len(clean_entries),
        "selection_stats": selection_stats,
        "selected_profiles": filtered_profiles,
        "source_run_root": str(source_root),
        "cleaning": {
            "generated_at_utc": utc_iso(),
            "source_selected_count": len(entries),
            "removed_count": len(bad_ids),
            "kept_count": len(clean_entries),
            "issue_counts": {key: int(value) for key, value in issue_counter.items()},
            "removed_by_split": {key: int(value) for key, value in split_removed_counter.items()},
            "removed_by_diagram_type": {key: int(value) for key, value in diagram_removed_counter.items()},
            "rules": [
                "drop boundary_count_mismatch",
                "drop boundary_not_exact",
                "drop duplicate_turn_ids",
            ],
            "example_removed_samples": issue_examples,
        },
    }
    write_json(selection_output / "selection_manifest.json", clean_manifest)
    write_json(output_root / "cleaning_manifest.json", clean_manifest["cleaning"])

    report_output.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at_utc": utc_iso(),
        "source_run_root": str(source_root),
        "output_run_root": str(output_root),
        "source_selected_count": len(entries),
        "clean_selected_count": len(clean_entries),
        "removed_count": len(bad_ids),
        "kept_rate": round(len(clean_entries) / len(entries), 4) if entries else None,
        "issue_counts": {key: int(value) for key, value in issue_counter.items()},
        "removed_by_split": {key: int(value) for key, value in split_removed_counter.items()},
        "removed_by_diagram_type": {key: int(value) for key, value in diagram_removed_counter.items()},
        "clean_split_sizes": {key: len(value) for key, value in split_ids.items()},
        "example_removed_samples": issue_examples,
    }
    write_json(report_output / "clean_derivation.summary.json", summary)
    (report_output / "clean_derivation.summary.md").write_text(
        "\n".join(
            [
                "# Incremental Clean Derivation",
                "",
                f"- Source run root: `{source_root}`",
                f"- Output run root: `{output_root}`",
                f"- Source selected count: {len(entries)}",
                f"- Clean selected count: {len(clean_entries)}",
                f"- Removed count: {len(bad_ids)}",
                f"- Kept rate: {summary['kept_rate']}",
                "",
                "## Issue Counts",
                "",
                *[f"- `{key}`: {value}" for key, value in summary["issue_counts"].items()],
                "",
                "## Removed By Split",
                "",
                *[f"- `{key}`: {value}" for key, value in summary["removed_by_split"].items()],
                "",
                "## Removed By Diagram Type",
                "",
                *[f"- `{key}`: {value}" for key, value in summary["removed_by_diagram_type"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Output run root: {output_root}")
    print(f"Selection manifest: {selection_output / 'selection_manifest.json'}")
    print(f"Cleaning manifest: {output_root / 'cleaning_manifest.json'}")
    print(f"Report JSON: {report_output / 'clean_derivation.summary.json'}")


if __name__ == "__main__":
    main()
