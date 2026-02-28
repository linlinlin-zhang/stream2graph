#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtime frontend server for Stream2Graph.

Provides:
- Static web UI serving
- API bridge to realtime backend pipeline
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "versions" / "v3_2026-02-27_latest_9k_cscw" / "scripts"
FRONTEND_DIR = REPO_ROOT / "frontend" / "realtime_ui"
EXPERIMENT_REPORTS_DIR = REPO_ROOT / "reports" / "experiment_reports"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from asr_stream_adapter import ASRChunk  # noqa: E402
from evaluate_realtime_pipeline import evaluate_payload  # noqa: E402
from incremental_renderer import IncrementalGraphRenderer  # noqa: E402
from run_realtime_pipeline import run_realtime_pipeline  # noqa: E402
from streaming_intent_engine import EngineConfig, StreamingIntentEngine, StreamingUpdate, TranscriptChunk  # noqa: E402
from unified_pretrain_eval import evaluate_dataset, merge_scores  # noqa: E402

SESSION_LOCK = threading.Lock()
SESSIONS: Dict[str, "SessionState"] = {}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _evaluate_with_thresholds(pipeline: Dict, payload: Dict) -> Dict:
    return evaluate_payload(
        payload=pipeline,
        latency_p95_threshold_ms=float(payload.get("latency_p95_threshold_ms", 2000.0)),
        flicker_mean_threshold=float(payload.get("flicker_mean_threshold", 6.0)),
        mental_map_min=float(payload.get("mental_map_min", 0.85)),
        intent_acc_threshold=float(payload.get("intent_accuracy_threshold", 0.8)),
    )


def _extract_summary(
    pipeline: Optional[Dict],
    realtime_eval: Optional[Dict],
    unified_eval: Optional[Dict],
) -> Dict:
    p_summary = (pipeline or {}).get("summary", {}) if isinstance(pipeline, dict) else {}
    p_stability = p_summary.get("renderer_stability", {}) if isinstance(p_summary, dict) else {}
    r_metrics = (realtime_eval or {}).get("metrics", {}) if isinstance(realtime_eval, dict) else {}

    readiness = {}
    if isinstance(unified_eval, dict):
        if isinstance(unified_eval.get("pretrain_readiness"), dict):
            readiness = unified_eval.get("pretrain_readiness", {})
        else:
            readiness = unified_eval

    return {
        "updates_emitted": p_summary.get("updates_emitted"),
        "latency_e2e_p95_ms": r_metrics.get("e2e_latency_p95_ms", p_summary.get("latency_e2e_ms", {}).get("p95")),
        "intent_accuracy": r_metrics.get("intent_accuracy", p_summary.get("intent_labeled_accuracy")),
        "flicker_mean": r_metrics.get(
            "flicker_index_mean",
            (p_stability.get("flicker_index", {}) if isinstance(p_stability, dict) else {}).get("mean"),
        ),
        "mental_map_mean": r_metrics.get(
            "mental_map_score_mean",
            (p_stability.get("mental_map_score", {}) if isinstance(p_stability, dict) else {}).get("mean"),
        ),
        "realtime_eval_pass": (realtime_eval or {}).get("realtime_eval_pass"),
        "overall_pretrain_readiness_score": readiness.get("overall_pretrain_readiness_score"),
        "pretrain_recommendation": readiness.get("recommendation"),
    }


def _build_experiment_report_md(report: Dict) -> str:
    checks = {}
    if isinstance(report.get("realtime_evaluation"), dict):
        checks = report["realtime_evaluation"].get("checks", {}) or {}

    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Experiment Report",
        "",
        f"- Generated at (UTC): {report.get('generated_at_utc')}",
        f"- Title: {report.get('title') or 'Untitled'}",
        f"- Session ID: {report.get('session_id') or '-'}",
        "",
        "## Summary",
        "",
        f"- Updates emitted: {summary.get('updates_emitted')}",
        f"- E2E P95 (ms): {summary.get('latency_e2e_p95_ms')}",
        f"- Intent accuracy: {summary.get('intent_accuracy')}",
        f"- Flicker mean: {summary.get('flicker_mean')}",
        f"- Mental map mean: {summary.get('mental_map_mean')}",
        f"- Realtime pass: {summary.get('realtime_eval_pass')}",
        f"- Pretrain readiness score: {summary.get('overall_pretrain_readiness_score')}",
        f"- Pretrain recommendation: {summary.get('pretrain_recommendation')}",
        "",
    ]
    if checks:
        lines.extend(["## Realtime Checks", ""])
        for key in sorted(checks.keys()):
            val = checks.get(key)
            lines.append(f"- {key}: {'PASS' if val else 'FAIL'}")
        lines.append("")
    notes = str(report.get("notes", "")).strip()
    if notes:
        lines.extend(["## Notes", "", notes, ""])
    return "\n".join(lines) + "\n"


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
        if not label:
            continue
        if start_ms <= ts <= end_ms:
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]


@dataclass
class SessionState:
    session_id: str
    config: EngineConfig
    engine: StreamingIntentEngine
    renderer: IncrementalGraphRenderer
    created_wall_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    lock: threading.Lock = field(default_factory=threading.Lock)
    events: List[Dict] = field(default_factory=list)
    labeled_chunks: List[Tuple[int, Optional[str]]] = field(default_factory=list)
    chunk_count: int = 0
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    e2e_latencies: List[float] = field(default_factory=list)
    update_latencies: List[float] = field(default_factory=list)
    render_latencies: List[float] = field(default_factory=list)

    def ingest_chunk(self, chunk: TranscriptChunk, expected_intent: Optional[str]) -> List[Dict]:
        if self.first_ts is None:
            self.first_ts = chunk.timestamp_ms
        self.last_ts = chunk.timestamp_ms
        self.chunk_count += 1
        self.labeled_chunks.append((chunk.timestamp_ms, expected_intent))

        updates = self.engine.ingest(chunk)
        return self._consume_updates(updates)

    def flush(self) -> List[Dict]:
        updates = self.engine.flush()
        return self._consume_updates(updates)

    def _consume_updates(self, updates: Sequence[StreamingUpdate]) -> List[Dict]:
        emitted: List[Dict] = []
        for update in updates:
            render_t0 = int(time.time() * 1000)
            frame = self.renderer.apply_update(
                update_id=update.update_id,
                operations=update.operations,
                intent_type=update.intent_type,
            )
            render_ms = int(time.time() * 1000) - render_t0
            e2e_ms = float(update.processing_latency_ms + render_ms)
            gold_intent = _majority_label_in_range(
                labeled_chunks=self.labeled_chunks,
                start_ms=update.start_ms,
                end_ms=update.end_ms,
            )
            event = {
                "update": asdict(update),
                "render_frame": asdict(frame),
                "gold_intent": gold_intent,
                "intent_correct": (gold_intent == update.intent_type) if gold_intent else None,
                "render_latency_ms": render_ms,
                "e2e_latency_ms": round(e2e_ms, 4),
            }
            self.events.append(event)
            emitted.append(event)
            self.e2e_latencies.append(e2e_ms)
            self.update_latencies.append(float(update.processing_latency_ms))
            self.render_latencies.append(float(render_ms))
        return emitted

    def pipeline_payload(self, mode: str = "live_session") -> Dict:
        runtime_ms = int(time.time() * 1000) - self.created_wall_ms
        transcript_duration_ms = 0
        if self.first_ts is not None and self.last_ts is not None:
            transcript_duration_ms = max(0, self.last_ts - self.first_ts)
        speed_vs_realtime = (
            round(transcript_duration_ms / runtime_ms, 4)
            if runtime_ms > 0 and transcript_duration_ms > 0
            else 0.0
        )

        prediction_pairs = []
        for ev in self.events:
            gold = ev.get("gold_intent")
            pred = ev.get("update", {}).get("intent_type")
            prediction_pairs.append((gold, pred))
        labeled_eval_count = len([1 for g, _ in prediction_pairs if g is not None])
        labeled_correct = len([1 for g, p in prediction_pairs if g is not None and g == p])
        labeled_accuracy = (labeled_correct / labeled_eval_count) if labeled_eval_count > 0 else None

        return {
            "meta": {
                "mode": mode,
                "time_scale": 1.0,
                "input_chunk_count": self.chunk_count,
                "runtime_ms": runtime_ms,
                "transcript_duration_ms": transcript_duration_ms,
                "speedup_vs_realtime": speed_vs_realtime,
            },
            "summary": {
                "updates_emitted": len(self.events),
                "latency_e2e_ms": _stats(self.e2e_latencies),
                "latency_update_ms": _stats(self.update_latencies),
                "latency_render_ms": _stats(self.render_latencies),
                "intent_labeled_eval_count": labeled_eval_count,
                "intent_labeled_accuracy": round(labeled_accuracy, 4) if labeled_accuracy is not None else None,
                "intent_runtime_distribution": self.engine.get_runtime_report().get("intent_distribution", {}),
                "boundary_distribution": self.engine.get_runtime_report().get("boundary_distribution", {}),
                "renderer_stability": self.renderer.summary(),
            },
            "engine_report": self.engine.get_runtime_report(),
            "renderer_state": self.renderer.export_state(),
            "events": self.events,
        }


def _json_response(handler: SimpleHTTPRequestHandler, payload: Dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: SimpleHTTPRequestHandler) -> Dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _safe_subpath(path_value: str) -> Optional[Path]:
    p = Path(path_value).expanduser().resolve()
    try:
        p.relative_to(REPO_ROOT)
        return p
    except Exception:
        return None


def _build_chunks(payload: Dict) -> List[ASRChunk]:
    chunks_data = payload.get("chunks", [])
    if isinstance(chunks_data, list) and chunks_data:
        chunks: List[ASRChunk] = []
        for i, row in enumerate(chunks_data):
            if not isinstance(row, dict):
                continue
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            ts = row.get("timestamp_ms")
            if ts is None:
                ts = i * 450
            chunks.append(
                ASRChunk(
                    timestamp_ms=int(ts),
                    text=text,
                    speaker=str(row.get("speaker", "user")),
                    is_final=bool(row.get("is_final", True)),
                    expected_intent=row.get("expected_intent"),
                    metadata=row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {},
                )
            )
        chunks.sort(key=lambda x: x.timestamp_ms)
        return chunks

    text = str(payload.get("transcript_text", "")).strip()
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks = []
    for i, ln in enumerate(lines):
        parts = [p.strip() for p in ln.split("|")]
        # Supported quick format:
        # text
        # speaker|text
        # speaker|text|expected_intent
        if len(parts) == 1:
            speaker = "user"
            txt = parts[0]
            expected = None
        elif len(parts) == 2:
            speaker = parts[0] or "user"
            txt = parts[1]
            expected = None
        else:
            speaker = parts[0] or "user"
            txt = parts[1]
            expected = parts[2] or None
        if not txt:
            continue
        chunks.append(
            ASRChunk(
                timestamp_ms=i * 450,
                text=txt,
                speaker=speaker,
                is_final=True,
                expected_intent=expected,
            )
        )
    return chunks


class RealtimeUIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str = str(FRONTEND_DIR), **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            _json_response(
                self,
                {
                    "ok": True,
                    "service": "stream2graph-realtime-ui-server",
                    "repo_root": str(REPO_ROOT),
                    "frontend_dir": str(FRONTEND_DIR),
                    "active_sessions": len(SESSIONS),
                },
            )
            return
        if parsed.path == "/api/config":
            _json_response(
                self,
                {
                    "ok": True,
                    "default_dataset_dir": str(
                        REPO_ROOT
                        / "versions"
                        / "v3_2026-02-27_latest_9k_cscw"
                        / "dataset"
                        / "stream2graph_dataset"
                        / "compliant_v3_repaired_20260228"
                    ),
                    "default_realtime_thresholds": {
                        "latency_p95_threshold_ms": 2000.0,
                        "flicker_mean_threshold": 6.0,
                        "mental_map_min": 0.85,
                        "intent_accuracy_threshold": 0.8,
                    },
                    "speech_recognition_hint": "browser_web_speech_api",
                    "experiment_report_dir": str(EXPERIMENT_REPORTS_DIR),
                },
            )
            return
        if parsed.path == "/api/session/list":
            with SESSION_LOCK:
                items = sorted(
                    [
                        {
                            "session_id": sid,
                            "chunk_count": sess.chunk_count,
                            "updates_emitted": len(sess.events),
                        }
                        for sid, sess in SESSIONS.items()
                    ],
                    key=lambda x: x["session_id"],
                )
            _json_response(self, {"ok": True, "sessions": items})
            return
        if parsed.path == "/api/report/list":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["20"])[0])
            except Exception:
                limit = 20
            limit = max(1, min(limit, 100))

            EXPERIMENT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            items: List[Dict] = []
            files = sorted(
                [
                    p
                    for p in EXPERIMENT_REPORTS_DIR.glob("EXPERIMENT_REPORT_*.json")
                    if p.name != "EXPERIMENT_REPORT_LATEST.json"
                ],
                reverse=True,
            )
            for p in files[:limit]:
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    items.append(
                        {
                            "filename": p.name,
                            "generated_at_utc": raw.get("generated_at_utc"),
                            "title": raw.get("title"),
                            "session_id": raw.get("session_id"),
                            "summary": raw.get("summary"),
                        }
                    )
                except Exception:
                    items.append({"filename": p.name})
            _json_response(self, {"ok": True, "count": len(items), "reports": items})
            return
        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = _read_json_body(self)

        if parsed.path == "/api/session/create":
            config = EngineConfig(
                min_wait_k=int(payload.get("min_wait_k", 1)),
                base_wait_k=int(payload.get("base_wait_k", 2)),
                max_wait_k=int(payload.get("max_wait_k", 4)),
            )
            session_id = uuid.uuid4().hex[:12]
            sess = SessionState(
                session_id=session_id,
                config=config,
                engine=StreamingIntentEngine(config=config),
                renderer=IncrementalGraphRenderer(),
            )
            with SESSION_LOCK:
                SESSIONS[session_id] = sess
            _json_response(
                self,
                {
                    "ok": True,
                    "session_id": session_id,
                    "config": asdict(config),
                },
            )
            return

        if parsed.path == "/api/session/chunk":
            session_id = str(payload.get("session_id", "")).strip()
            text = str(payload.get("text", "")).strip()
            if not session_id:
                _json_response(self, {"ok": False, "error": "session_id required"}, status=400)
                return
            if not text:
                _json_response(self, {"ok": False, "error": "text required"}, status=400)
                return
            with SESSION_LOCK:
                sess = SESSIONS.get(session_id)
            if sess is None:
                _json_response(self, {"ok": False, "error": "session not found"}, status=404)
                return

            timestamp_ms = payload.get("timestamp_ms")
            if timestamp_ms is None:
                if sess.last_ts is None:
                    timestamp_ms = 0
                else:
                    timestamp_ms = sess.last_ts + 450

            tchunk = TranscriptChunk(
                timestamp_ms=int(timestamp_ms),
                text=text,
                speaker=str(payload.get("speaker", "user")),
                is_final=bool(payload.get("is_final", True)),
            )
            expected_intent = payload.get("expected_intent")

            with sess.lock:
                emitted = sess.ingest_chunk(tchunk, expected_intent=expected_intent)
                summary = sess.pipeline_payload(mode="live_session")

            _json_response(
                self,
                {
                    "ok": True,
                    "session_id": session_id,
                    "emitted_events": emitted,
                    "session_summary": summary.get("summary", {}),
                    "events_total": len(summary.get("events", [])),
                },
            )
            return

        if parsed.path == "/api/session/flush":
            session_id = str(payload.get("session_id", "")).strip()
            if not session_id:
                _json_response(self, {"ok": False, "error": "session_id required"}, status=400)
                return
            with SESSION_LOCK:
                sess = SESSIONS.get(session_id)
            if sess is None:
                _json_response(self, {"ok": False, "error": "session not found"}, status=404)
                return

            with sess.lock:
                emitted = sess.flush()
                pipeline = sess.pipeline_payload(mode="live_session")
                evaluation = _evaluate_with_thresholds(pipeline, payload)

            if bool(payload.get("close_after_flush", True)):
                with SESSION_LOCK:
                    SESSIONS.pop(session_id, None)

            _json_response(
                self,
                {
                    "ok": True,
                    "session_id": session_id,
                    "emitted_events": emitted,
                    "pipeline": pipeline,
                    "evaluation": evaluation,
                    "closed": bool(payload.get("close_after_flush", True)),
                },
            )
            return

        if parsed.path == "/api/session/snapshot":
            session_id = str(payload.get("session_id", "")).strip()
            if not session_id:
                _json_response(self, {"ok": False, "error": "session_id required"}, status=400)
                return
            with SESSION_LOCK:
                sess = SESSIONS.get(session_id)
            if sess is None:
                _json_response(self, {"ok": False, "error": "session not found"}, status=404)
                return

            include_eval = bool(payload.get("include_evaluation", True))
            with sess.lock:
                pipeline = sess.pipeline_payload(mode="live_session")
                evaluation = _evaluate_with_thresholds(pipeline, payload) if include_eval else None
            _json_response(
                self,
                {
                    "ok": True,
                    "session_id": session_id,
                    "pipeline": pipeline,
                    "evaluation": evaluation,
                },
            )
            return

        if parsed.path == "/api/session/close":
            session_id = str(payload.get("session_id", "")).strip()
            if not session_id:
                _json_response(self, {"ok": False, "error": "session_id required"}, status=400)
                return
            with SESSION_LOCK:
                removed = SESSIONS.pop(session_id, None)
            _json_response(self, {"ok": True, "closed": removed is not None, "session_id": session_id})
            return

        if parsed.path == "/api/pipeline/run":
            chunks = _build_chunks(payload)
            if not chunks:
                _json_response(self, {"ok": False, "error": "no transcript chunks provided"}, status=400)
                return

            config = EngineConfig(
                min_wait_k=int(payload.get("min_wait_k", 1)),
                base_wait_k=int(payload.get("base_wait_k", 2)),
                max_wait_k=int(payload.get("max_wait_k", 4)),
            )
            result = run_realtime_pipeline(
                chunks=chunks,
                realtime=bool(payload.get("realtime", False)),
                time_scale=float(payload.get("time_scale", 1.0)),
                max_chunks=int(payload.get("max_chunks", 0)),
                config=config,
            )
            _json_response(self, {"ok": True, "result": result})
            return

        if parsed.path == "/api/pipeline/evaluate":
            chunks = _build_chunks(payload)
            if not chunks:
                _json_response(self, {"ok": False, "error": "no transcript chunks provided"}, status=400)
                return

            config = EngineConfig(
                min_wait_k=int(payload.get("min_wait_k", 1)),
                base_wait_k=int(payload.get("base_wait_k", 2)),
                max_wait_k=int(payload.get("max_wait_k", 4)),
            )
            pipeline_result = run_realtime_pipeline(
                chunks=chunks,
                realtime=bool(payload.get("realtime", False)),
                time_scale=float(payload.get("time_scale", 1.0)),
                max_chunks=int(payload.get("max_chunks", 0)),
                config=config,
            )

            eval_result = _evaluate_with_thresholds(pipeline_result, payload)
            _json_response(self, {"ok": True, "pipeline": pipeline_result, "evaluation": eval_result})
            return

        if parsed.path == "/api/pretrain/unified":
            dataset_dir_input = str(payload.get("dataset_dir", "")).strip()
            if not dataset_dir_input:
                _json_response(self, {"ok": False, "error": "dataset_dir required"}, status=400)
                return
            dataset_dir = _safe_subpath(dataset_dir_input)
            if dataset_dir is None or not dataset_dir.exists():
                _json_response(self, {"ok": False, "error": "dataset_dir must exist inside repository"}, status=400)
                return

            dataset_eval = evaluate_dataset(str(dataset_dir), max_files=int(payload.get("max_files", 0)))

            realtime_eval_payload = payload.get("realtime_evaluation")
            if isinstance(realtime_eval_payload, dict):
                checks = realtime_eval_payload.get("checks", {})
                if isinstance(checks, dict) and checks:
                    pass_ratio = sum(1 for v in checks.values() if v) / max(len(checks), 1)
                    realtime_eval = {
                        "found": True,
                        "realtime_score": round(pass_ratio * 100.0, 2),
                        "checks": checks,
                        "metrics": realtime_eval_payload.get("metrics", {}),
                    }
                else:
                    realtime_eval = None
            else:
                realtime_eval = None

            merged = merge_scores(dataset_eval, realtime_eval)
            _json_response(
                self,
                {
                    "ok": True,
                    "dataset_evaluation": dataset_eval,
                    "realtime_evaluation": realtime_eval,
                    "pretrain_readiness": merged,
                },
            )
            return

        if parsed.path == "/api/report/save":
            EXPERIMENT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

            session_id = str(payload.get("session_id", "")).strip() or None
            title = str(payload.get("title", "")).strip() or "stream2graph_experiment"
            notes = str(payload.get("notes", "")).strip()

            pipeline = payload.get("pipeline_result")
            if not isinstance(pipeline, dict):
                pipeline = payload.get("pipeline")
            realtime_eval = payload.get("realtime_evaluation")
            if not isinstance(realtime_eval, dict):
                realtime_eval = payload.get("evaluation")
            unified_eval = payload.get("unified_evaluation")
            if not isinstance(unified_eval, dict):
                unified_eval = payload.get("pretrain_readiness")

            if session_id and not isinstance(pipeline, dict):
                with SESSION_LOCK:
                    sess = SESSIONS.get(session_id)
                if sess is not None:
                    with sess.lock:
                        pipeline = sess.pipeline_payload(mode="live_session")

            if isinstance(pipeline, dict) and not isinstance(realtime_eval, dict):
                realtime_eval = _evaluate_with_thresholds(pipeline, payload)

            report = {
                "generated_at_utc": _utc_iso(),
                "title": title,
                "session_id": session_id,
                "notes": notes,
                "summary": _extract_summary(pipeline, realtime_eval, unified_eval),
                "pipeline_result": pipeline,
                "realtime_evaluation": realtime_eval,
                "unified_evaluation": unified_eval,
            }

            ts = _utc_tag()
            json_path = EXPERIMENT_REPORTS_DIR / f"EXPERIMENT_REPORT_{ts}.json"
            md_path = EXPERIMENT_REPORTS_DIR / f"EXPERIMENT_REPORT_{ts}.md"
            latest_json = EXPERIMENT_REPORTS_DIR / "EXPERIMENT_REPORT_LATEST.json"
            latest_md = EXPERIMENT_REPORTS_DIR / "EXPERIMENT_REPORT_LATEST.md"

            json_text = json.dumps(report, ensure_ascii=False, indent=2)
            md_text = _build_experiment_report_md(report)
            json_path.write_text(json_text, encoding="utf-8")
            md_path.write_text(md_text, encoding="utf-8")
            latest_json.write_text(json_text, encoding="utf-8")
            latest_md.write_text(md_text, encoding="utf-8")

            _json_response(
                self,
                {
                    "ok": True,
                    "report": report,
                    "files": {
                        "json": str(json_path.relative_to(REPO_ROOT)),
                        "md": str(md_path.relative_to(REPO_ROOT)),
                        "latest_json": str(latest_json.relative_to(REPO_ROOT)),
                        "latest_md": str(latest_md.relative_to(REPO_ROOT)),
                    },
                },
            )
            return

        _json_response(self, {"ok": False, "error": f"unknown endpoint: {parsed.path}"}, status=404)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Stream2Graph realtime frontend and API.")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), RealtimeUIHandler)
    print(f"[stream2graph-ui] http://{args.host}:{args.port}")
    print(f"[stream2graph-ui] frontend: {FRONTEND_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
