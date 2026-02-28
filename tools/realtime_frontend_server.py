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
from dataclasses import asdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "versions" / "v3_2026-02-27_latest_9k_cscw" / "scripts"
FRONTEND_DIR = REPO_ROOT / "frontend" / "realtime_ui"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from asr_stream_adapter import ASRChunk  # noqa: E402
from evaluate_realtime_pipeline import evaluate_payload  # noqa: E402
from run_realtime_pipeline import run_realtime_pipeline  # noqa: E402
from streaming_intent_engine import EngineConfig  # noqa: E402
from unified_pretrain_eval import evaluate_dataset, merge_scores  # noqa: E402


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
                },
            )
            return
        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = _read_json_body(self)

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

            eval_result = evaluate_payload(
                payload=pipeline_result,
                latency_p95_threshold_ms=float(payload.get("latency_p95_threshold_ms", 2000.0)),
                flicker_mean_threshold=float(payload.get("flicker_mean_threshold", 6.0)),
                mental_map_min=float(payload.get("mental_map_min", 0.85)),
                intent_acc_threshold=float(payload.get("intent_accuracy_threshold", 0.8)),
            )
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
