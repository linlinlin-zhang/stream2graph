from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import get_settings


settings = get_settings()
REPO_ROOT = settings.repo_root
SCRIPTS_DIR = REPO_ROOT / "versions" / "v3_2026-02-27_latest_9k_cscw" / "scripts"
TOOLS_DIR = REPO_ROOT / "tools"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from asr_stream_adapter import ASRChunk  # noqa: E402
from evaluate_realtime_pipeline import evaluate_payload  # noqa: E402
from incremental_renderer import IncrementalGraphRenderer  # noqa: E402
from run_realtime_pipeline import run_realtime_pipeline  # noqa: E402
from streaming_intent_engine import EngineConfig, StreamingIntentEngine, StreamingUpdate, TranscriptChunk  # noqa: E402
from tools.eval.dataset import load_evaluation_samples  # noqa: E402
from tools.eval.metrics import MermaidCompileChecker, score_prediction  # noqa: E402
from tools.eval.predictors import build_predictor  # noqa: E402


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


def _stats(values: List[float]) -> Dict[str, float]:
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
    return max(counts.items(), key=lambda item: item[1])[0]


@dataclass
class RuntimeSessionState:
    session_id: str
    config: EngineConfig
    engine: StreamingIntentEngine
    renderer: IncrementalGraphRenderer
    created_wall_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    events: List[Dict[str, Any]] = field(default_factory=list)
    labeled_chunks: List[Tuple[int, Optional[str]]] = field(default_factory=list)
    chunk_count: int = 0
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    e2e_latencies: List[float] = field(default_factory=list)
    update_latencies: List[float] = field(default_factory=list)
    render_latencies: List[float] = field(default_factory=list)

    def ingest_chunk(self, chunk: TranscriptChunk, expected_intent: Optional[str]) -> List[Dict[str, Any]]:
        if self.first_ts is None:
            self.first_ts = chunk.timestamp_ms
        self.last_ts = chunk.timestamp_ms
        self.chunk_count += 1
        self.labeled_chunks.append((chunk.timestamp_ms, expected_intent))
        updates = self.engine.ingest(chunk)
        return self._consume_updates(updates)

    def flush(self) -> List[Dict[str, Any]]:
        updates = self.engine.flush()
        return self._consume_updates(updates)

    def _consume_updates(self, updates: Sequence[StreamingUpdate]) -> List[Dict[str, Any]]:
        emitted: List[Dict[str, Any]] = []
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

    def pipeline_payload(self, mode: str = "live_session") -> Dict[str, Any]:
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
            prediction_pairs.append((ev.get("gold_intent"), ev.get("update", {}).get("intent_type")))
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


def new_runtime_session(session_id: str, *, min_wait_k: int, base_wait_k: int, max_wait_k: int) -> RuntimeSessionState:
    config = EngineConfig(
        min_wait_k=min_wait_k,
        base_wait_k=base_wait_k,
        max_wait_k=max_wait_k,
    )
    return RuntimeSessionState(
        session_id=session_id,
        config=config,
        engine=StreamingIntentEngine(config=config),
        renderer=IncrementalGraphRenderer(),
    )


def restore_runtime_session(session_id: str, config_snapshot: dict[str, Any], rows: list[dict[str, Any]]) -> RuntimeSessionState:
    runtime = new_runtime_session(
        session_id,
        min_wait_k=int(config_snapshot.get("min_wait_k", 1)),
        base_wait_k=int(config_snapshot.get("base_wait_k", 2)),
        max_wait_k=int(config_snapshot.get("max_wait_k", 4)),
    )
    for row in rows:
        runtime.ingest_chunk(
            TranscriptChunk(
                timestamp_ms=int(row["timestamp_ms"]),
                text=str(row["text"]),
                speaker=str(row.get("speaker", "user")),
                is_final=bool(row.get("is_final", True)),
            ),
            expected_intent=row.get("expected_intent"),
        )
    return runtime


def run_sample_compare(
    *,
    dataset_dir: str,
    split_dir: str,
    split: str,
    sample_id: str,
    predictors: list[dict[str, Any]],
    compile_command: str = "",
) -> dict[str, Any]:
    samples = load_evaluation_samples(
        source_dir=dataset_dir,
        split_dir=split_dir,
        split=split,
        sample_ids={sample_id},
    )
    if not samples:
        raise ValueError(f"sample not found: {sample_id}")
    sample = samples[0]
    compile_checker = MermaidCompileChecker(compile_command) if compile_command else None

    rows: list[dict[str, Any]] = []
    for predictor_config in predictors:
        predictor = build_predictor(predictor_config)
        try:
            result = predictor.predict(sample)
        finally:
            predictor.close()
        metrics = score_prediction(
            reference_code=sample.reference_code,
            predicted_code=result.generated_code,
            declared_diagram_type=sample.diagram_type,
            compile_checker=compile_checker,
        )
        rows.append(
            {
                "provider": result.provider,
                "model_name": result.model_name,
                "generated_code": result.generated_code,
                "raw_output_text": result.raw_output_text,
                "latency_ms": result.latency_ms,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "error": result.error,
                "metrics": metrics,
            }
        )

    return {
        "sample": {
            "sample_id": sample.sample_id,
            "split": sample.split,
            "diagram_type": sample.diagram_type,
            "dialogue_turns": sample.dialogue_turns,
            "source_path": sample.source_path,
            "reference_code": sample.reference_code,
            "prompt": sample.prompt,
            "metadata": sample.metadata,
        },
        "predictions": rows,
    }


def run_realtime_payload(
    chunks: list[dict[str, Any]],
    *,
    realtime: bool,
    time_scale: float,
    min_wait_k: int,
    base_wait_k: int,
    max_wait_k: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    asr_chunks = [
        ASRChunk(
            timestamp_ms=int(item["timestamp_ms"]),
            text=str(item["text"]),
            speaker=str(item.get("speaker", "user")),
            is_final=bool(item.get("is_final", True)),
            expected_intent=item.get("expected_intent"),
            metadata=item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {},
        )
        for item in chunks
    ]
    payload = run_realtime_pipeline(
        chunks=asr_chunks,
        realtime=realtime,
        time_scale=time_scale,
        max_chunks=0,
        config=EngineConfig(min_wait_k=min_wait_k, base_wait_k=base_wait_k, max_wait_k=max_wait_k),
    )
    evaluation = evaluate_payload(payload)
    return payload, evaluation


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown_artifact(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_temp_config(payload: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def run_eval_suite_subprocess(config_payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    config_path = write_temp_config(config_payload, output_dir)
    import subprocess

    command = [
        sys.executable,
        str(REPO_ROOT / "tools" / "eval" / "run_eval_suite.py"),
        "--config",
        str(config_path),
    ]
    started_at = time.time()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    stdout_path = output_dir / "suite.stdout.log"
    stderr_path = output_dir / "suite.stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    return {
        "command": command,
        "returncode": completed.returncode,
        "duration_seconds": round(time.time() - started_at, 3),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "config_path": str(config_path),
    }


def maybe_compile_mermaid(code: str) -> dict[str, Any] | None:
    if not settings.mermaid_compile_command:
        return None
    checker = MermaidCompileChecker(settings.mermaid_compile_command)
    return checker.check(code)
