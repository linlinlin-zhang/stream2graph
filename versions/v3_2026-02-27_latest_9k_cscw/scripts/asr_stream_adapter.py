#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASR stream adapter for realtime Stream2Graph pipeline.

This adapter supports JSON/JSONL transcript files and replays them in realtime
based on timestamp gaps. It is designed as an ASR boundary layer:
ASR output -> normalized chunks -> intent engine.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional

from streaming_intent_engine import TranscriptChunk


@dataclass
class ASRChunk:
    timestamp_ms: int
    text: str
    speaker: str = "user"
    is_final: bool = True
    expected_intent: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    arrive_wall_ms: int = 0

    def to_transcript_chunk(self) -> TranscriptChunk:
        return TranscriptChunk(
            timestamp_ms=self.timestamp_ms,
            text=self.text,
            speaker=self.speaker,
            is_final=self.is_final,
        )


def _load_json_rows(path: str) -> List[Dict]:
    if path.endswith(".jsonl"):
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        rows = payload.get("chunks", [])
        if isinstance(rows, list):
            return rows
    if isinstance(payload, list):
        return payload
    return []


def load_asr_chunks(path: str, default_interval_ms: int = 450) -> List[ASRChunk]:
    rows = _load_json_rows(path)
    chunks: List[ASRChunk] = []
    auto_ts = 0
    for row in rows:
        ts = row.get("timestamp_ms")
        if ts is None:
            ts = auto_ts
            auto_ts += default_interval_ms

        txt = str(row.get("text", "")).strip()
        if not txt:
            continue

        chunks.append(
            ASRChunk(
                timestamp_ms=int(ts),
                text=txt,
                speaker=str(row.get("speaker", "user")),
                is_final=bool(row.get("is_final", True)),
                expected_intent=row.get("expected_intent"),
                metadata=row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {},
            )
        )

    chunks.sort(key=lambda x: x.timestamp_ms)
    return chunks


class ASRStreamAdapter:
    def __init__(self, chunks: Iterable[ASRChunk]):
        self.chunks: List[ASRChunk] = sorted(list(chunks), key=lambda x: x.timestamp_ms)

    @classmethod
    def from_file(cls, path: str, default_interval_ms: int = 450) -> "ASRStreamAdapter":
        return cls(load_asr_chunks(path, default_interval_ms=default_interval_ms))

    def stream(
        self,
        realtime: bool = False,
        time_scale: float = 1.0,
        max_chunks: int = 0,
    ) -> Iterator[ASRChunk]:
        prev_ts: Optional[int] = None
        emitted = 0

        for chunk in self.chunks:
            if max_chunks > 0 and emitted >= max_chunks:
                break

            if realtime and prev_ts is not None:
                gap = max(0, chunk.timestamp_ms - prev_ts)
                if gap > 0:
                    speed = max(time_scale, 1e-6)
                    time.sleep((gap / 1000.0) / speed)

            chunk.arrive_wall_ms = int(time.time() * 1000)
            yield chunk
            prev_ts = chunk.timestamp_ms
            emitted += 1
