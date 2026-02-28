#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streaming Intent Engine (Step 2)

Purpose:
- Consume real-time transcript chunks.
- Detect semantic boundaries online.
- Infer intent with confidence.
- Dispatch incremental graph operations with adaptive wait-k.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass
from statistics import mean, median
from typing import Deque, Dict, Iterable, List, Optional, Tuple


INTENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "sequential": (
        "first",
        "then",
        "next",
        "after",
        "before",
        "finally",
        "step",
        "loop",
        "if",
        "else",
        "while",
        "start",
        "end",
        "flow",
        "流程",
        "步骤",
        "然后",
        "之后",
    ),
    "structural": (
        "component",
        "module",
        "service",
        "gateway",
        "layer",
        "architecture",
        "system",
        "dependency",
        "interface",
        "模块",
        "架构",
        "服务",
        "依赖",
        "接口",
    ),
    "classification": (
        "category",
        "group",
        "type",
        "branch",
        "cluster",
        "tree",
        "tag",
        "分类",
        "分组",
        "层级",
        "分支",
    ),
    "relational": (
        "entity",
        "table",
        "schema",
        "relationship",
        "join",
        "foreign",
        "primary",
        "关联",
        "关系",
        "实体",
        "表",
        "主键",
        "外键",
    ),
    "contrastive": (
        "compare",
        "versus",
        "vs",
        "difference",
        "ratio",
        "percentage",
        "contrast",
        "对比",
        "差异",
        "占比",
        "趋势",
    ),
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "for",
    "and",
    "or",
    "we",
    "you",
    "it",
    "is",
    "are",
    "be",
    "this",
    "that",
    "with",
    "as",
    "by",
    "把",
    "的",
    "了",
    "在",
    "和",
    "与",
    "并",
    "就",
    "先",
    "再",
    "一个",
    "这里",
    "这个",
    "那个",
}

BOUNDARY_MARKERS = (
    "然后",
    "接着",
    "另外",
    "最后",
    "next",
    "then",
    "finally",
    "meanwhile",
)


@dataclass
class TranscriptChunk:
    timestamp_ms: int
    text: str
    speaker: str = "user"
    is_final: bool = True


@dataclass
class EngineConfig:
    min_wait_k: int = 1
    base_wait_k: int = 2
    max_wait_k: int = 4
    min_boundary_tokens: int = 6
    silence_boundary_ms: int = 1200
    max_window_ms: int = 3800
    token_budget_per_wait_k: int = 18


@dataclass
class StreamingUpdate:
    update_id: int
    start_ms: int
    end_ms: int
    duration_ms: int
    boundary_reason: str
    intent_type: str
    intent_confidence: float
    wait_k_used: int
    token_count: int
    chunk_count: int
    keywords: List[str]
    operations: List[Dict]
    transcript_text: str
    processing_latency_ms: int


def tokenize(text: str) -> List[str]:
    raw = (text or "").lower()
    chunks = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", raw)
    tokens: List[str] = []
    for ch in chunks:
        if re.fullmatch(r"[\u4e00-\u9fff]+", ch):
            if len(ch) <= 3:
                tokens.append(ch)
                continue
            # Lightweight CJK chunking: keep every 2-char piece for online stats.
            for i in range(0, len(ch), 2):
                piece = ch[i : i + 2]
                if len(piece) >= 2:
                    tokens.append(piece)
        else:
            tokens.append(ch)
    return [t for t in tokens if t and t not in STOPWORDS]


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return float(min(values))
    if p >= 100:
        return float(max(values))
    arr = sorted(values)
    idx = int(round((len(arr) - 1) * (p / 100.0)))
    return float(arr[idx])


class OnlineIntentClassifier:
    def __init__(self) -> None:
        self.keyword_index: Dict[str, str] = {}
        for intent, words in INTENT_KEYWORDS.items():
            for w in words:
                self.keyword_index[w.lower()] = intent

    def classify(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        raw = (text or "").lower()
        tokens = tokenize(raw)
        if not tokens:
            return "generic", 0.35, {"generic": 1.0}

        scores = Counter()
        for t in tokens:
            intent = self.keyword_index.get(t)
            if intent:
                scores[intent] += 1
        # Chinese keywords may appear in longer phrases without spaces.
        for kw, intent in self.keyword_index.items():
            if re.search(r"[\u4e00-\u9fff]", kw) and kw in raw:
                scores[intent] += 1

        if not scores:
            # No obvious pattern: infer weakly as generic.
            conf = min(0.42 + len(tokens) / 100.0, 0.55)
            return "generic", round(conf, 4), {"generic": round(conf, 4)}

        top_intent, top_hits = scores.most_common(1)[0]
        total_hits = sum(scores.values())
        score_ratio = top_hits / max(total_hits, 1)
        density = min(total_hits / max(len(tokens), 1), 1.0)
        confidence = 0.45 + 0.4 * score_ratio + 0.15 * density
        confidence = max(0.35, min(confidence, 0.96))

        score_map = {k: round(v / max(total_hits, 1), 4) for k, v in scores.items()}
        return top_intent, round(confidence, 4), score_map


class StreamingIntentEngine:
    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self.classifier = OnlineIntentClassifier()
        self.pending: Deque[TranscriptChunk] = deque()
        self.pending_arrive_wall_ms: Deque[int] = deque()
        self.pending_tokens = 0
        self.current_wait_k = self.config.base_wait_k
        self.update_id = 0
        self.last_chunk_ts: Optional[int] = None
        self.last_keywords: List[str] = []
        self.metrics: Dict[str, List[float]] = {
            "latency_ms": [],
            "update_duration_ms": [],
            "tokens_per_update": [],
        }
        self.intent_counter: Counter = Counter()
        self.boundary_counter: Counter = Counter()

    def ingest(self, chunk: TranscriptChunk) -> List[StreamingUpdate]:
        text = (chunk.text or "").strip()
        if not text:
            return []

        gap_ms = 0
        if self.last_chunk_ts is not None:
            gap_ms = max(0, chunk.timestamp_ms - self.last_chunk_ts)
        self.last_chunk_ts = chunk.timestamp_ms

        self.pending.append(chunk)
        self.pending_arrive_wall_ms.append(int(time.time() * 1000))
        self.pending_tokens += len(tokenize(text))

        reason = self._should_dispatch_reason(chunk, gap_ms)
        if reason is None:
            return []
        if len(self.pending) < self.current_wait_k and reason not in {
            "max_window_ms",
            "silence_gap",
        }:
            return []

        return [self._dispatch(reason)]

    def flush(self) -> List[StreamingUpdate]:
        if not self.pending:
            return []
        return [self._dispatch("stream_end")]

    def get_runtime_report(self) -> Dict:
        return {
            "updates_emitted": self.update_id,
            "current_wait_k": self.current_wait_k,
            "intent_distribution": dict(self.intent_counter),
            "boundary_distribution": dict(self.boundary_counter),
            "latency_ms": self._stats(self.metrics["latency_ms"]),
            "update_duration_ms": self._stats(self.metrics["update_duration_ms"]),
            "tokens_per_update": self._stats(self.metrics["tokens_per_update"]),
        }

    def _should_dispatch_reason(self, latest: TranscriptChunk, gap_ms: int) -> Optional[str]:
        if not self.pending:
            return None

        tokens = self.pending_tokens
        start_ms = self.pending[0].timestamp_ms
        window_ms = max(0, latest.timestamp_ms - start_ms)
        latest_text = (latest.text or "").strip()
        lower = latest_text.lower()
        ends_sentence = bool(re.search(r"[.!?。！？]$", latest_text))
        has_marker = any(lower.startswith(m) for m in BOUNDARY_MARKERS)

        if gap_ms >= self.config.silence_boundary_ms and tokens >= self.config.min_boundary_tokens:
            return "silence_gap"
        if window_ms >= self.config.max_window_ms:
            return "max_window_ms"
        if ends_sentence and tokens >= self.config.min_boundary_tokens:
            return "sentence_end"
        if has_marker and tokens >= self.config.min_boundary_tokens:
            return "discourse_marker"
        if tokens >= self.current_wait_k * self.config.token_budget_per_wait_k:
            return "token_budget"
        return None

    def _dispatch(self, reason: str) -> StreamingUpdate:
        self.update_id += 1
        chunks = list(self.pending)
        arrive_times = list(self.pending_arrive_wall_ms)
        self.pending.clear()
        self.pending_arrive_wall_ms.clear()
        self.pending_tokens = 0

        start_ms = chunks[0].timestamp_ms
        end_ms = chunks[-1].timestamp_ms
        duration_ms = max(0, end_ms - start_ms)
        joined = " ".join((c.text or "").strip() for c in chunks if (c.text or "").strip())
        tokens = tokenize(joined)
        intent_type, intent_conf, _ = self.classifier.classify(joined)
        keywords = self._extract_keywords(joined, tokens)
        novelty = self._semantic_novelty(keywords)
        self._update_wait_k(intent_conf, novelty)
        operations = self._build_incremental_ops(keywords, intent_type)
        now_ms = int(time.time() * 1000)
        process_latency_ms = max(0, now_ms - min(arrive_times)) if arrive_times else 0

        self.metrics["latency_ms"].append(process_latency_ms)
        self.metrics["update_duration_ms"].append(duration_ms)
        self.metrics["tokens_per_update"].append(len(tokens))
        self.intent_counter[intent_type] += 1
        self.boundary_counter[reason] += 1

        return StreamingUpdate(
            update_id=self.update_id,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
            boundary_reason=reason,
            intent_type=intent_type,
            intent_confidence=intent_conf,
            wait_k_used=self.current_wait_k,
            token_count=len(tokens),
            chunk_count=len(chunks),
            keywords=keywords,
            operations=operations,
            transcript_text=joined,
            processing_latency_ms=process_latency_ms,
        )

    def _extract_keywords(self, text: str, tokens: List[str], max_items: int = 8) -> List[str]:
        text_lower = (text or "").lower()
        domain_hits: List[str] = []
        for kw in sorted(self.classifier.keyword_index.keys(), key=lambda x: (-len(x), x)):
            if kw in text_lower:
                domain_hits.append(kw)

        phrase_candidates: List[str] = []
        for p in re.split(r"[，。！？；;,.!?]+", text):
            p = p.strip()
            if not p:
                continue
            if len(p) > 20:
                p = p[:20]
            if len(p) >= 2:
                phrase_candidates.append(p)

        alpha_freq = Counter(t for t in tokens if re.fullmatch(r"[a-z0-9_]{3,}", t))
        alpha_candidates = [k for k, _ in sorted(alpha_freq.items(), key=lambda x: (-x[1], -len(x[0]), x[0]))]

        merged: List[str] = []
        seen = set()
        for c in domain_hits + phrase_candidates + alpha_candidates:
            if not c:
                continue
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)
            if len(merged) >= max_items:
                break

        if not merged:
            return ["core_step"]
        return merged

    def _semantic_novelty(self, keywords: List[str]) -> float:
        if not self.last_keywords:
            self.last_keywords = keywords
            return 1.0
        prev = set(self.last_keywords)
        cur = set(keywords)
        union = prev | cur
        if not union:
            self.last_keywords = keywords
            return 0.0
        overlap = len(prev & cur) / len(union)
        novelty = 1.0 - overlap
        self.last_keywords = keywords
        return novelty

    def _update_wait_k(self, confidence: float, novelty: float) -> None:
        wait_k = self.config.base_wait_k
        if confidence >= 0.78 and novelty <= 0.35:
            wait_k += 1
        if confidence < 0.52 or novelty >= 0.8:
            wait_k -= 1
        wait_k = max(self.config.min_wait_k, min(wait_k, self.config.max_wait_k))
        self.current_wait_k = wait_k

    def _build_incremental_ops(self, keywords: List[str], intent_type: str) -> List[Dict]:
        ops: List[Dict] = []
        node_ids: List[str] = []
        for i, kw in enumerate(keywords[:6], start=1):
            nid = f"u{self.update_id}_n{i}"
            node_ids.append(nid)
            ops.append(
                {
                    "op": "add_node",
                    "id": nid,
                    "label": kw,
                    "intent": intent_type,
                }
            )

        if intent_type in {"sequential", "contrastive"} and len(node_ids) >= 2:
            for src, dst in zip(node_ids[:-1], node_ids[1:]):
                ops.append({"op": "add_edge", "from": src, "to": dst})
        elif intent_type in {"relational", "structural"} and len(node_ids) >= 2:
            hub = node_ids[0]
            for n in node_ids[1:]:
                ops.append({"op": "add_edge", "from": hub, "to": n})
        return ops

    def _stats(self, values: List[float]) -> Dict[str, float]:
        if not values:
            return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
        return {
            "count": float(len(values)),
            "mean": round(float(mean(values)), 3),
            "p50": round(float(median(values)), 3),
            "p95": round(percentile(values, 95), 3),
            "max": round(float(max(values)), 3),
        }


def run_streaming_intent_engine(
    chunks: Iterable[TranscriptChunk],
    config: Optional[EngineConfig] = None,
) -> Tuple[List[StreamingUpdate], Dict]:
    engine = StreamingIntentEngine(config=config)
    updates: List[StreamingUpdate] = []
    for ck in chunks:
        updates.extend(engine.ingest(ck))
    updates.extend(engine.flush())
    report = engine.get_runtime_report()
    return updates, report


def _read_chunks(path: str) -> List[TranscriptChunk]:
    if path.endswith(".jsonl"):
        rows: List[TranscriptChunk] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                rows.append(
                    TranscriptChunk(
                        timestamp_ms=int(item.get("timestamp_ms", 0)),
                        text=str(item.get("text", "")),
                        speaker=str(item.get("speaker", "user")),
                        is_final=bool(item.get("is_final", True)),
                    )
                )
        return rows

    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict):
        obj = obj.get("chunks", [])
    rows = []
    for item in obj:
        rows.append(
            TranscriptChunk(
                timestamp_ms=int(item.get("timestamp_ms", 0)),
                text=str(item.get("text", "")),
                speaker=str(item.get("speaker", "user")),
                is_final=bool(item.get("is_final", True)),
            )
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streaming intent engine for real-time transcript parsing.")
    parser.add_argument("--input", type=str, required=True, help="Input transcript JSON/JSONL path.")
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output JSON path for emitted updates + runtime report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = _read_chunks(args.input)
    chunks = sorted(chunks, key=lambda x: x.timestamp_ms)
    updates, report = run_streaming_intent_engine(chunks)

    payload = {
        "update_count": len(updates),
        "updates": [asdict(u) for u in updates],
        "runtime_report": report,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
