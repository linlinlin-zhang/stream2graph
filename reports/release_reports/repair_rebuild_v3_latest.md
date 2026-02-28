# V3 Repair And Rebuild Report

- Built at: 2026-02-28T13:41:51Z
- Source: `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/cscw_dialogue_dataset`

## Counts

- Input records: 9000
- Repaired full set: 9000
- Training-ready set: 9000
- Compliant set: 8607

## Recovery

- Compilation recovered (local): 3794
- Compilation recovered (kroki fallback): 209
- License recovered: 52
- Source recovered: 48
- Diagram type recovered: 48
- Dialogue repaired (trim/pad): 150

## Compilation Audit

- Audit sample size: 200
- Audit pass: 200
- Audit fail: 0
- Audit pass rate: 1.0

## Remaining Unresolved

- invalid_license: 393

## Top Rejection Reasons For Compliant Set

- invalid_or_missing_license: 393

## Output Paths

- Repaired full: `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/repaired_v3_20260228`
- Train-ready: `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/train_v3_repaired_20260228`
- Compliant: `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/compliant_v3_repaired_20260228`
- Unresolved index: `reports/release_reports/repair_rebuild_v3_unresolved_20260228_133941.json`