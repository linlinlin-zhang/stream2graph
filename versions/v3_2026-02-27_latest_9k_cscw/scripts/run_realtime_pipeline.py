#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end realtime pipeline:
ASR -> intent inference -> incremental rendering.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from statistics import mean, median
from typing import Dict, List, Optional, Sequence, Tuple

from asr_stream_adapter import ASRChunk, ASRStreamAdapter, load_asr_chunks
from incremental_renderer import IncrementalGraphRenderer
from streaming_intent_engine import EngineConfig, StreamingIntentEngine, StreamingUpdate


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


def _majority_label_in_range(
    labeled_chunks: Sequence[Tuple[int, Optional[str]]],
    start_ms: int,
    end_ms: int,
) -> Optional[str]:
    counts: Dict[str, int] = {}
    for ts, label in labeled_chunks:
        if label is None:
            continue
        if start_ms <= ts <= end_ms:
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]


def run_realtime_pipeline(
    chunks: Sequence[ASRChunk],
    realtime: bool = False,
    time_scale: float = 1.0,
    max_chunks: int = 0,
    config: Optional[EngineConfig] = None,
) -> Dict:
    adapter = ASRStreamAdapter(chunks)
    engine = StreamingIntentEngine(config=config or EngineConfig())
    renderer = IncrementalGraphRenderer()

    events: List[Dict] = []
    labeled_chunks: List[Tuple[int, Optional[str]]] = []
    e2e_latencies: List[float] = []
    render_latencies: List[float] = []
    update_latencies: List[float] = []
    prediction_pairs: List[Tuple[Optional[str], str]] = []

    wall_start_ms = int(time.time() * 1000)

    def consume_update(update: StreamingUpdate) -> None:
        render_t0 = int(time.time() * 1000)
        frame = renderer.apply_update(
            update_id=update.update_id,
            operations=update.operations,
            intent_type=update.intent_type,
        )
        render_ms = int(time.time() * 1000) - render_t0
        e2e_ms = float(update.processing_latency_ms + render_ms)
        gold_intent = _majority_label_in_range(
            labeled_chunks=labeled_chunks,
            start_ms=update.start_ms,
            end_ms=update.end_ms,
        )
        prediction_pairs.append((gold_intent, update.intent_type))

        e2e_latencies.append(e2e_ms)
        render_latencies.append(float(render_ms))
        update_latencies.append(float(update.processing_latency_ms))

        events.append(
            {
                "update": asdict(update),
                "render_frame": asdict(frame),
                "gold_intent": gold_intent,
                "intent_correct": (gold_intent == update.intent_type) if gold_intent else None,
                "render_latency_ms": render_ms,
                "e2e_latency_ms": round(e2e_ms, 4),
            }
        )

    for asr_chunk in adapter.stream(realtime=realtime, time_scale=time_scale, max_chunks=max_chunks):
        labeled_chunks.append((asr_chunk.timestamp_ms, asr_chunk.expected_intent))
        updates = engine.ingest(asr_chunk.to_transcript_chunk())
        for u in updates:
            consume_update(u)

    flush_updates = engine.flush()
    for u in flush_updates:
        consume_update(u)

    wall_end_ms = int(time.time() * 1000)
    transcript_duration_ms = 0
    if chunks:
        transcript_duration_ms = max(0, chunks[-1].timestamp_ms - chunks[0].timestamp_ms)
    runtime_ms = max(0, wall_end_ms - wall_start_ms)
    speed_vs_realtime = (
        round(transcript_duration_ms / runtime_ms, 4) if runtime_ms > 0 and transcript_duration_ms > 0 else 0.0
    )

    labeled_eval_count = len([1 for g, _ in prediction_pairs if g is not None])
    labeled_correct = len([1 for g, p in prediction_pairs if g is not None and g == p])
    labeled_accuracy = (labeled_correct / labeled_eval_count) if labeled_eval_count > 0 else None

    return {
        "meta": {
            "mode": "realtime" if realtime else "offline_replay",
            "time_scale": time_scale,
            "input_chunk_count": len(chunks),
            "runtime_ms": runtime_ms,
            "transcript_duration_ms": transcript_duration_ms,
            "speedup_vs_realtime": speed_vs_realtime,
        },
        "summary": {
            "updates_emitted": len(events),
            "latency_e2e_ms": _stats(e2e_latencies),
            "latency_update_ms": _stats(update_latencies),
            "latency_render_ms": _stats(render_latencies),
            "intent_labeled_eval_count": labeled_eval_count,
            "intent_labeled_accuracy": round(labeled_accuracy, 4) if labeled_accuracy is not None else None,
            "intent_runtime_distribution": engine.get_runtime_report().get("intent_distribution", {}),
            "boundary_distribution": engine.get_runtime_report().get("boundary_distribution", {}),
            "renderer_stability": renderer.summary(),
        },
        "engine_report": engine.get_runtime_report(),
        "renderer_state": renderer.export_state(),
        "events": events,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stream2Graph realtime end-to-end pipeline.")
    parser.add_argument("--input", type=str, required=True, help="Transcript JSON/JSONL path.")
    parser.add_argument("--output", type=str, default="", help="Optional JSON output report path.")
    parser.add_argument("--realtime", action="store_true", help="Replay transcript with realtime delays.")
    parser.add_argument("--time-scale", type=float, default=1.0, help="Realtime speed factor (>1 faster).")
    parser.add_argument("--max-chunks", type=int, default=0, help="Optional max chunk count.")
    parser.add_argument("--min-wait-k", type=int, default=1)
    parser.add_argument("--base-wait-k", type=int, default=2)
    parser.add_argument("--max-wait-k", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_asr_chunks(args.input)
    config = EngineConfig(
        min_wait_k=args.min_wait_k,
        base_wait_k=args.base_wait_k,
        max_wait_k=args.max_wait_k,
    )
    payload = run_realtime_pipeline(
        chunks=chunks,
        realtime=args.realtime,
        time_scale=args.time_scale,
        max_chunks=args.max_chunks,
        config=config,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
