from __future__ import annotations

from app.legacy import new_runtime_session


def test_runtime_session_emits_pipeline_payload() -> None:
    runtime = new_runtime_session("test", min_wait_k=1, base_wait_k=2, max_wait_k=4)
    runtime.ingest_chunk(
        chunk=type("Chunk", (), {"timestamp_ms": 0, "text": "First define gateway and parser.", "speaker": "expert", "is_final": True})(),
        expected_intent="sequential",
    )
    payload = runtime.pipeline_payload()
    assert "summary" in payload
    assert payload["meta"]["input_chunk_count"] == 1
