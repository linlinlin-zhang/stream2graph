# Core Algorithm Upgrade Report (Step 2)

- Date (UTC): 2026-02-28
- Scope:
  - `streaming_intent_engine.py`
  - `benchmark_streaming_intent.py`

## Goal
Add real-time core algorithm capability on top of Step 1 offline engine:
- Online transcript ingestion
- Semantic boundary detection
- Online intent detection
- Adaptive wait-k dispatch
- Latency-oriented benchmark

## Implemented in Step 2
1. Streaming intent engine
- New file: `streaming_intent_engine.py`
- Added `TranscriptChunk`, `EngineConfig`, `StreamingUpdate` data structures.
- Added online pipeline:
  - ingest transcript chunk
  - boundary detection (`sentence_end`, `silence_gap`, `discourse_marker`, `max_window_ms`, `token_budget`)
  - intent classification with confidence
  - adaptive wait-k policy update
  - incremental operation emission (`add_node`, `add_edge`)

2. Chinese-friendly online parsing improvements
- Added mixed tokenization for English + Chinese.
- Added Chinese keyword substring matching in intent classifier.
- Reworked keyword extraction:
  - domain keyword hits first
  - phrase-level cues second
  - alphanumeric fallback last
- This prevents unreadable short fragments from dominating node labels.

3. Runtime metrics
- Engine now records:
  - intent distribution
  - boundary reason distribution
  - processing latency stats
  - update duration stats
  - tokens/update stats

4. Benchmark script
- New file: `benchmark_streaming_intent.py`
- Supports:
  - file input benchmark (JSON/JSONL transcript)
  - synthetic benchmark generation
  - report output + update output

## Validation
1. Compile check
```bash
python3 -m py_compile \
  /home/lin-server/pictures/streaming_intent_engine.py \
  /home/lin-server/pictures/benchmark_streaming_intent.py
```

2. Synthetic benchmark smoke
```bash
python3 /home/lin-server/pictures/benchmark_streaming_intent.py \
  --synthetic-samples 180 \
  --output-report /home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset_v2_smoke/_streaming_benchmark_step2.json \
  --output-updates /home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset_v2_smoke/_streaming_updates_step2.json
```

Result snapshot:
- input chunks: 180
- output updates: 141
- runtime: 95.99 ms
- transcript duration: 71,860 ms
- speedup vs realtime: 748.618x
- latency p95: 1.0 ms (processing latency, offline replay setting)

3. Chinese transcript smoke
```bash
python3 /home/lin-server/pictures/streaming_intent_engine.py \
  --input /tmp/streaming_transcript_sample.json \
  --output /tmp/streaming_intent_engine_sample_output.json
```

Observed:
- intent recognized as `structural`
- boundary trigger: `sentence_end`
- output keyword labels now readable (`服务`, `模块`, `依赖`, `接口`, ...)

## Known Gaps After Step 2
1. Intent classification is keyword-heuristic, not yet a learned model.
2. Benchmark currently reports offline replay latency, not true end-to-end ASR-to-render latency.
3. Incremental operations are generic graph ops, not yet bound to front-end renderer protocol.
4. No A/B comparison yet against Step 1 on user-facing interaction quality.

## Next Step (Step 3)
- Integrate streaming engine with front-end render protocol:
  - stable element IDs across updates
  - patch-based update strategy (diff instead of append-only)
  - flicker suppression metrics
- Add real transcript benchmark:
  - ASR chunk jitter simulation
  - intent precision/recall against labeled stream windows
