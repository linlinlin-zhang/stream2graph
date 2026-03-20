# Incremental Dataset Analysis

- Generated at (UTC): 2026-03-20T16:35:29Z
- Run root: `E:\Desktop\stream2graph\data\incremental_dataset\runs\minimax_m27_incremental_full_v1_clean`

## Overview

| Metric | Value |
| --- | --- |
| sample_count | 2861 |
| load_error_count | 0 |
| boundary_exact_rate | 1.0 |
| monotonic_graph_rate | 1.0 |
| stage_count_match_rate | 1.0 |
| preview_present_rate | 1.0 |
| nonempty_delta_stage_rate | 0.8818 |

## Core Numeric Metrics

| Metric | Mean | P50 | P95 | Min | Max |
| --- | --- | --- | --- | --- | --- |
| turn_count | 10.1643 | 8.0 | 23.0 | 1.0 | 62.0 |
| stage_count | 1.9934 | 1.0 | 5.0 | 1.0 | 5.0 |
| turn_tokens_per_dialogue | 473.1349 | 399.0 | 1043.0 | 0.0 | 2240.0 |
| turn_tokens_per_turn | 46.5488 | 44.0 | 84.0 | 0.0 | 270.0 |
| final_nodes | 6.4579 | 4.0 | 29.0 | 0.0 | 93.0 |
| final_edges | 0.1171 | 0.0 | 0.0 | 0.0 | 17.0 |
| final_groups | 1.4876 | 0.0 | 9.0 | 0.0 | 25.0 |
| final_entities | 8.0626 | 4.0 | 36.0 | 0.0 | 93.0 |
| turns_per_stage | 6.0287 | 5.0 | 12.0 | 1.0 | 27.0 |
| delta_ops_per_stage | 4.0447 | 3.0 | 11.0 | 0.0 | 24.0 |
| actual_entity_growth_per_stage | 4.0447 | 3.0 | 11.0 | 0.0 | 24.0 |
| final_edge_density | 0.0048 | 0.0 | 0.0 | 0.0 | 0.6667 |

## By Diagram Type

| Diagram Type | Count | Avg Turns | Avg Stages | Avg Final Entities | Avg Delta Ops/Stage | Avg Actual Growth/Stage | Boundary Exact Rate | Monotonic Graph Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| architecture | 619 | 14.8805 | 3.4507 | 17.0662 | 4.5949 | 4.5949 | 1.0 | 1.0 |
| er | 69 | 6.0 | 1.058 | 0.2754 | 0.1739 | 0.1739 | 1.0 | 1.0 |
| flowchart | 623 | 10.7961 | 2.3515 | 9.1091 | 2.7303 | 2.7303 | 1.0 | 1.0 |
| mindmap | 335 | 11.2716 | 2.4269 | 10.6507 | 3.3493 | 3.3493 | 1.0 | 1.0 |
| sequence | 593 | 8.9831 | 1.0 | 5.3963 | 5.3963 | 5.3963 | 1.0 | 1.0 |
| statediagram | 622 | 5.8296 | 1.0016 | 0.0659 | 0.0627 | 0.0627 | 1.0 | 1.0 |

## Split Distribution

| Split | Count |
| --- | --- |
| train | 2281 |
| validation | 297 |
| test | 283 |

## Diagram Distribution

| Diagram Type | Count |
| --- | --- |
| flowchart | 623 |
| statediagram | 622 |
| architecture | 619 |
| sequence | 593 |
| mindmap | 335 |
| er | 69 |
