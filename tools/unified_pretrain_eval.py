#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified pre-training evaluation for Stream2Graph.

Combines:
1) Dataset readiness checks
2) Optional realtime pipeline evaluation import
3) Unified readiness scoring before model training/fine-tuning
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from statistics import mean, median
from typing import Dict, List, Optional


INVALID_LICENSE_VALUES = {"none", "unknown", "error", "rate_limited", ""}


def _safe_ratio(a: int, b: int) -> float:
    return (a / b) if b > 0 else 0.0


def _pctl(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    if p <= 0:
        return float(arr[0])
    if p >= 100:
        return float(arr[-1])
    idx = int(round((len(arr) - 1) * p / 100.0))
    return float(arr[idx])


def _stats(values: List[float]) -> Dict:
    if not values:
        return {"count": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": float(len(values)),
        "mean": round(float(mean(values)), 4),
        "p50": round(float(median(values)), 4),
        "p95": round(float(_pctl(values, 95.0)), 4),
        "max": round(float(max(values)), 4),
    }


def evaluate_dataset(dataset_dir: str, max_files: int = 0) -> Dict:
    files = sorted(glob.glob(os.path.join(dataset_dir, "*.json")))
    if max_files > 0:
        files = files[:max_files]

    total = len(files)
    schema_ok = 0
    code_ok = 0
    dialogue_ok = 0
    turn_range_ok = 0
    compile_ok = 0
    license_ok = 0
    diagram_type_ok = 0
    parse_fail = 0

    diagram_types: Dict[str, int] = {}
    turn_counts: List[float] = []

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            parse_fail += 1
            continue

        has_id = bool(obj.get("id") or obj.get("record_id"))
        has_code = isinstance(obj.get("code"), str) and len(obj.get("code", "")) > 0
        has_diagram_type = isinstance(obj.get("diagram_type"), str) and len(obj.get("diagram_type", "")) > 0
        dialogue = obj.get("cscw_dialogue")
        has_dialogue = isinstance(dialogue, list) and len(dialogue) > 0
        schema_pass = has_id and has_code and has_diagram_type and has_dialogue

        if schema_pass:
            schema_ok += 1
        if has_code:
            code_ok += 1
        if has_dialogue:
            dialogue_ok += 1

        if has_dialogue:
            turns = len(dialogue)
            turn_counts.append(float(turns))
            if 4 <= turns <= 120:
                turn_range_ok += 1

        comp = str(obj.get("compilation_status", "")).strip().lower()
        if comp == "success":
            compile_ok += 1

        raw_license = str(obj.get("license_name") or obj.get("license") or "").strip().lower()
        if raw_license not in INVALID_LICENSE_VALUES:
            license_ok += 1

        if has_diagram_type:
            diagram_type_ok += 1
            d = obj.get("diagram_type")
            diagram_types[d] = diagram_types.get(d, 0) + 1

    unique_types = len(diagram_types)
    schema_ratio = _safe_ratio(schema_ok, total)
    compile_ratio = _safe_ratio(compile_ok, total)
    license_ratio = _safe_ratio(license_ok, total)
    turn_range_ratio = _safe_ratio(turn_range_ok, dialogue_ok)
    diversity_ratio = min(unique_types / 10.0, 1.0)

    dataset_score = (
        0.30 * schema_ratio
        + 0.20 * compile_ratio
        + 0.15 * license_ratio
        + 0.20 * turn_range_ratio
        + 0.15 * diversity_ratio
    )
    dataset_score = round(dataset_score * 100.0, 2)

    return {
        "dataset_dir": dataset_dir,
        "file_count": total,
        "parse_fail_count": parse_fail,
        "ratios": {
            "schema_ratio": round(schema_ratio, 4),
            "code_ratio": round(_safe_ratio(code_ok, total), 4),
            "dialogue_ratio": round(_safe_ratio(dialogue_ok, total), 4),
            "turn_range_ratio": round(turn_range_ratio, 4),
            "compile_success_ratio": round(compile_ratio, 4),
            "license_valid_ratio": round(license_ratio, 4),
            "diagram_type_present_ratio": round(_safe_ratio(diagram_type_ok, total), 4),
            "diagram_diversity_ratio": round(diversity_ratio, 4),
        },
        "turn_stats": _stats(turn_counts),
        "diagram_type_top": sorted(diagram_types.items(), key=lambda x: (-x[1], x[0]))[:20],
        "unique_diagram_types": unique_types,
        "dataset_readiness_score": dataset_score,
    }


def evaluate_realtime_report(realtime_report_path: str) -> Optional[Dict]:
    if not realtime_report_path:
        return None
    if not os.path.exists(realtime_report_path):
        return None

    with open(realtime_report_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    checks = obj.get("checks", {})
    if not checks:
        return {
            "found": True,
            "realtime_score": 0.0,
            "detail": obj,
        }

    pass_ratio = _safe_ratio(sum(1 for v in checks.values() if v), len(checks))
    realtime_score = round(pass_ratio * 100.0, 2)
    return {
        "found": True,
        "realtime_score": realtime_score,
        "checks": checks,
        "metrics": obj.get("metrics", {}),
    }


def merge_scores(dataset_eval: Dict, realtime_eval: Optional[Dict]) -> Dict:
    dataset_score = float(dataset_eval.get("dataset_readiness_score", 0.0))
    if realtime_eval and realtime_eval.get("found"):
        realtime_score = float(realtime_eval.get("realtime_score", 0.0))
        final_score = round(0.7 * dataset_score + 0.3 * realtime_score, 2)
        mode = "dataset+realtime"
    else:
        realtime_score = None
        final_score = round(dataset_score, 2)
        mode = "dataset_only"

    ready = final_score >= 80.0
    recommendation = (
        "ready_for_finetuning"
        if ready
        else "improve_data_or_realtime_metrics_before_finetuning"
    )

    return {
        "mode": mode,
        "dataset_score": dataset_score,
        "realtime_score": realtime_score,
        "overall_pretrain_readiness_score": final_score,
        "ready": ready,
        "recommendation": recommendation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified pre-training evaluation for Stream2Graph.")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Dataset directory containing JSON records.")
    parser.add_argument("--realtime-report", type=str, default="", help="Optional realtime evaluation report JSON.")
    parser.add_argument("--max-files", type=int, default=0, help="Optional max file count for quick checks.")
    parser.add_argument("--output", type=str, default="", help="Optional output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_eval = evaluate_dataset(args.dataset_dir, max_files=args.max_files)
    realtime_eval = evaluate_realtime_report(args.realtime_report)
    merged = merge_scores(dataset_eval, realtime_eval)

    payload = {
        "dataset_evaluation": dataset_eval,
        "realtime_evaluation": realtime_eval,
        "pretrain_readiness": merged,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
