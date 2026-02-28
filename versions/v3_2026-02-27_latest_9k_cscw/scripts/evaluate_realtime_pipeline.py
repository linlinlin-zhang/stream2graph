#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtime evaluation for Stream2Graph end-to-end pipeline.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional, Tuple

from asr_stream_adapter import load_asr_chunks
from run_realtime_pipeline import run_realtime_pipeline
from streaming_intent_engine import EngineConfig


def _macro_f1(pairs: List[Tuple[Optional[str], str]]) -> Optional[float]:
    filtered = [(g, p) for g, p in pairs if g is not None]
    if not filtered:
        return None
    labels = sorted(set([g for g, _ in filtered] + [p for _, p in filtered]))
    f1s: List[float] = []
    for lb in labels:
        tp = sum(1 for g, p in filtered if g == lb and p == lb)
        fp = sum(1 for g, p in filtered if g != lb and p == lb)
        fn = sum(1 for g, p in filtered if g == lb and p != lb)
        denom = 2 * tp + fp + fn
        f1 = (2 * tp / denom) if denom > 0 else 0.0
        f1s.append(f1)
    return sum(f1s) / max(len(f1s), 1)


def _collect_pairs(events: List[Dict]) -> List[Tuple[Optional[str], str]]:
    pairs: List[Tuple[Optional[str], str]] = []
    for e in events:
        gold = e.get("gold_intent")
        pred = e.get("update", {}).get("intent_type")
        if pred is None:
            continue
        pairs.append((gold, str(pred)))
    return pairs


def evaluate_payload(
    payload: Dict,
    latency_p95_threshold_ms: float = 2000.0,
    flicker_mean_threshold: float = 6.0,
    mental_map_min: float = 0.85,
    intent_acc_threshold: float = 0.8,
) -> Dict:
    summary = payload.get("summary", {})
    meta = payload.get("meta", {})
    renderer = summary.get("renderer_stability", {})

    e2e_p95 = float(summary.get("latency_e2e_ms", {}).get("p95", 0.0))
    flicker_mean = float(renderer.get("flicker_index", {}).get("mean", 0.0))
    mental_mean = float(renderer.get("mental_map_score", {}).get("mean", 0.0))
    intent_acc = summary.get("intent_labeled_accuracy")
    intent_acc = float(intent_acc) if intent_acc is not None else None

    pairs = _collect_pairs(payload.get("events", []))
    macro_f1 = _macro_f1(pairs)

    checks = {
        "latency_p95_ok": e2e_p95 <= latency_p95_threshold_ms,
        "flicker_mean_ok": flicker_mean <= flicker_mean_threshold,
        "mental_map_ok": mental_mean >= mental_map_min,
        "intent_accuracy_ok": True if intent_acc is None else (intent_acc >= intent_acc_threshold),
    }
    overall_pass = all(checks.values())

    transcript_ms = float(meta.get("transcript_duration_ms", 0.0))
    runtime_ms = float(meta.get("runtime_ms", 0.0))
    realtime_factor = (runtime_ms / transcript_ms) if transcript_ms > 0 else None

    return {
        "realtime_eval_pass": overall_pass,
        "checks": checks,
        "thresholds": {
            "latency_p95_threshold_ms": latency_p95_threshold_ms,
            "flicker_mean_threshold": flicker_mean_threshold,
            "mental_map_min": mental_map_min,
            "intent_accuracy_threshold": intent_acc_threshold,
        },
        "metrics": {
            "mode": meta.get("mode"),
            "runtime_ms": runtime_ms,
            "transcript_duration_ms": transcript_ms,
            "runtime_over_transcript_ratio": round(realtime_factor, 4) if realtime_factor is not None else None,
            "e2e_latency_p95_ms": e2e_p95,
            "flicker_mean": flicker_mean,
            "mental_map_mean": mental_mean,
            "intent_accuracy": intent_acc,
            "intent_macro_f1": round(float(macro_f1), 4) if macro_f1 is not None else None,
            "updates_emitted": summary.get("updates_emitted"),
            "intent_labeled_eval_count": summary.get("intent_labeled_eval_count"),
        },
        "notes": [
            "intent metrics are only computed when expected_intent exists in transcript chunks",
            "realtime ratio around 1.0 indicates near real-time replay; <1.0 means faster-than-realtime processing",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Stream2Graph realtime end-to-end pipeline.")
    parser.add_argument("--input", type=str, required=True, help="Transcript JSON/JSONL path.")
    parser.add_argument("--pipeline-output", type=str, default="", help="Optional full pipeline output JSON.")
    parser.add_argument("--report-output", type=str, default="", help="Optional evaluation report JSON.")
    parser.add_argument("--realtime", action="store_true", help="Replay transcript in realtime.")
    parser.add_argument("--time-scale", type=float, default=1.0, help="Realtime replay speed (>1 faster).")
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--latency-p95-threshold-ms", type=float, default=2000.0)
    parser.add_argument("--flicker-mean-threshold", type=float, default=6.0)
    parser.add_argument("--mental-map-min", type=float, default=0.85)
    parser.add_argument("--intent-acc-threshold", type=float, default=0.8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_asr_chunks(args.input)
    payload = run_realtime_pipeline(
        chunks=chunks,
        realtime=args.realtime,
        time_scale=args.time_scale,
        max_chunks=args.max_chunks,
        config=EngineConfig(),
    )
    report = evaluate_payload(
        payload=payload,
        latency_p95_threshold_ms=args.latency_p95_threshold_ms,
        flicker_mean_threshold=args.flicker_mean_threshold,
        mental_map_min=args.mental_map_min,
        intent_acc_threshold=args.intent_acc_threshold,
    )

    if args.pipeline_output:
        with open(args.pipeline_output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    if args.report_output:
        with open(args.report_output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if not args.pipeline_output and not args.report_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
