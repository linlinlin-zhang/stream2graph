#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark script for streaming_intent_engine.py
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict
from typing import Dict, List, Tuple

from streaming_intent_engine import (
    EngineConfig,
    TranscriptChunk,
    run_streaming_intent_engine,
)


SYNTHETIC_PHRASES: Dict[str, List[str]] = {
    "sequential": [
        "First capture sensor data then normalize and filter the stream.",
        "Then compute feature windows and update the next step node.",
        "Finally write result to output stage and close the flow.",
    ],
    "structural": [
        "The gateway module connects to auth service and data service.",
        "Architecture has a storage layer, cache layer, and API layer.",
        "Add a dependency edge from scheduler component to worker pool.",
    ],
    "classification": [
        "Group these requirements into security, reliability, and performance categories.",
        "This branch should contain onboarding tasks and another branch for payment.",
        "Add a new category for observability and monitoring.",
    ],
    "relational": [
        "Entity user relates to order by one-to-many relationship.",
        "Order table links to payment table through foreign key order_id.",
        "Define schema relation for account and profile entities.",
    ],
    "contrastive": [
        "Compare baseline latency versus optimized latency in two lines.",
        "Show ratio difference between model A and model B.",
        "Add a contrast node for CPU and GPU throughput trends.",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the streaming intent engine.")
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Optional transcript input JSON/JSONL. If empty, synthetic data is generated.",
    )
    parser.add_argument("--synthetic-samples", type=int, default=120, help="Synthetic chunk count.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic generation.")
    parser.add_argument(
        "--output-report",
        type=str,
        default="",
        help="Optional report JSON output path.",
    )
    parser.add_argument(
        "--output-updates",
        type=str,
        default="",
        help="Optional updates JSON output path.",
    )
    return parser.parse_args()


def _load_chunks(path: str) -> List[TranscriptChunk]:
    if path.endswith(".jsonl"):
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                rows.append(
                    TranscriptChunk(
                        timestamp_ms=int(row.get("timestamp_ms", 0)),
                        text=str(row.get("text", "")),
                        speaker=str(row.get("speaker", "user")),
                        is_final=bool(row.get("is_final", True)),
                    )
                )
        return rows

    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict):
        obj = obj.get("chunks", [])
    rows = []
    for row in obj:
        rows.append(
            TranscriptChunk(
                timestamp_ms=int(row.get("timestamp_ms", 0)),
                text=str(row.get("text", "")),
                speaker=str(row.get("speaker", "user")),
                is_final=bool(row.get("is_final", True)),
            )
        )
    return rows


def _build_synthetic(n: int, seed: int = 42) -> Tuple[List[TranscriptChunk], Dict[str, int]]:
    rng = random.Random(seed)
    intents = list(SYNTHETIC_PHRASES.keys())
    rows: List[TranscriptChunk] = []
    target_counter = {k: 0 for k in intents}
    t = 0
    for _ in range(max(1, n)):
        intent = rng.choice(intents)
        text = rng.choice(SYNTHETIC_PHRASES[intent])
        target_counter[intent] += 1
        t += rng.randint(180, 640)
        rows.append(TranscriptChunk(timestamp_ms=t, text=text, speaker="expert", is_final=True))
    return rows, target_counter


def main() -> None:
    args = parse_args()

    if args.input:
        chunks = _load_chunks(args.input)
        synthetic_target = {}
        data_source = "input_file"
    else:
        chunks, synthetic_target = _build_synthetic(args.synthetic_samples, seed=args.seed)
        data_source = "synthetic"

    chunks = sorted(chunks, key=lambda x: x.timestamp_ms)
    start = time.time()
    updates, runtime_report = run_streaming_intent_engine(chunks, config=EngineConfig())
    elapsed_ms = (time.time() - start) * 1000.0

    transcript_duration_ms = 0
    if chunks:
        transcript_duration_ms = max(0, chunks[-1].timestamp_ms - chunks[0].timestamp_ms)

    benchmark_report = {
        "data_source": data_source,
        "input_chunk_count": len(chunks),
        "output_update_count": len(updates),
        "runtime_ms": round(elapsed_ms, 3),
        "transcript_duration_ms": transcript_duration_ms,
        "speedup_vs_realtime": round(transcript_duration_ms / max(elapsed_ms, 1e-9), 3)
        if transcript_duration_ms > 0
        else 0.0,
        "synthetic_intent_target": synthetic_target,
        "engine_runtime_report": runtime_report,
    }

    if args.output_report:
        with open(args.output_report, "w", encoding="utf-8") as f:
            json.dump(benchmark_report, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(benchmark_report, ensure_ascii=False, indent=2))

    if args.output_updates:
        with open(args.output_updates, "w", encoding="utf-8") as f:
            json.dump([asdict(u) for u in updates], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
