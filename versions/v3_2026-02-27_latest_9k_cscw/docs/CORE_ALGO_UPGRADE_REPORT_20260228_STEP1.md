# Core Algorithm Upgrade Report (Step 1)

- Date (UTC): 2026-02-28
- Scope: `cscw_dialogue_engine.py`, `run_reverse_engineering_v2.py`

## Goal
Upgrade the core reverse-engineering algorithm from a simple regex/template generator to a structured pipeline suitable for CSCW-grade experiments.

## Implemented in Step 1
1. Mermaid parser upgrade
- Added diagram-type detection (`flowchart`, `sequence`, `class`, `er`, `stateDiagram`, etc.).
- Added structured extraction of nodes, edges, and dependencies.
- Added fallback label extraction for noisy code.

2. Dynamic window planning
- Added dependency-level based segmentation.
- Added adaptive chunk size by diagram type and graph scale.

3. Wait-k incremental generation
- Added Wait-k batching (k=1/2 based on parse confidence).
- Execute turns now represent incremental commits rather than one-shot final output.

4. Intent-driven dialogue generation
- Added intent inference (`sequential`, `structural`, `classification`, `relational`, `contrastive`, `generic`).
- Added intent-specific proposal/clarify templates.
- Added repair turn trigger based on noise/confidence.

5. Metadata enrichment
- Added `algorithm_version`, `diagram_type_detected`, `intent_type`, `window_count`, `wait_k_used`, `parse_confidence`, `parser_warnings`, etc.

6. Runner upgrade
- `run_reverse_engineering_v2.py` now supports `--overwrite`, `--limit`, custom input/output/report paths.
- Generates `_generation_report_v2.json` with run stats and parser-warning summary.

## Smoke Test
Command:
```bash
python3 run_reverse_engineering_v2.py \
  --limit 12 \
  --overwrite \
  --output-dir /home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset_v2_smoke \
  --report-file /home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset_v2_smoke/_generation_report_v2.json
```

Result:
- processed: 12
- skipped: 0
- failed: 0
- runtime: 0.069s

## Known Gaps After Step 1
1. Some extreme noisy diagrams still produce ID-like labels (e.g., `n100`) instead of fully natural labels.
2. Real-time streaming components from the PDF plan are still missing:
- ASR stream listener
- semantic dynamic window over transcript stream
- online intent detector with latency constraints
- incremental front-end renderer and flicker control

## Next Step (Step 2)
- Build `streaming_intent_engine.py`:
  - transcript ingestion
  - semantic boundary detection
  - Wait-k dispatch policy
  - online intent scoring
- Add benchmark script for latency + intent detection precision.
