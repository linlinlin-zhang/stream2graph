# Stream2Graph 版本索引

## 总览

| 版本 | 时间锚点 | 主要目标 | 当前状态 |
| --- | --- | --- | --- |
| `v1_2026-02-05_legacy_8k_pipeline` | 2026-02-05 | 8k 五阶段流水线搭建 | 历史版本（结构保留） |
| `v2_2026-02-08_real_100percent_license_fix` | 2026-02-08 | 许可证修复/高质量筛选 | 历史版本（可追溯） |
| `v3_2026-02-27_latest_9k_cscw` | 2026-02-27 | 9k 数据合拢 + CSCW 对话生成 | 最新版本 |

## 版本细节

### 1) v1_2026-02-05_legacy_8k_pipeline

- 路径: `versions/v1_2026-02-05_legacy_8k_pipeline`
- 数据目录:
  - `01_curation`: 1 个索引 JSON
  - `02_filtering`: 1 个索引 JSON
  - `03_reverse_engineering`: 1 个索引 JSON
  - `04_validation`: 1 个索引 JSON
  - `05_final`: 8 个索引/统计 JSON（多数样本目录为空壳）
- 特点:
  - 保留了 8k 流水线设计与目录结构
  - 更适合看“方法框架”，不适合作为最终训练版本

### 2) v2_2026-02-08_real_100percent_license_fix

- 路径: `versions/v2_2026-02-08_real_100percent_license_fix`
- 数据目录:
  - `final_100percent_real`: 5603 JSON
  - `high_quality_subset`: 1827 JSON
  - `real_100percent_final`: 61 JSON
- 特点:
  - 重点在许可证修复、可编译性验证、高质量子集筛选
  - HuggingFace 数据在该阶段后已基本清空

### 3) v3_2026-02-27_latest_9k_cscw（最新）

- 路径: `versions/v3_2026-02-27_latest_9k_cscw`
- 数据目录:
  - `v3_verified_final`: 2649 JSON
  - `v4_industrial_source`: 351 JSON
  - `v5_augmented`: 6000 JSON
  - `final_v2_9k`: 9000 JSON
  - `dialogue_dataset`: 1346 JSON（旧版中间产物）
  - `cscw_dialogue_dataset`: 9000 JSON（当前主线对话数据）
- 特点:
  - 完成 9k 合并与 CSCW 对话逆向工程批处理
  - 这是当前最应优先使用的版本

### 4) v3 清洗发布集（2026-02-28）

- 路径:
  - `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_20260228`
- 构建脚本:
  - `tools/build_release_v3.py`
- 核心筛选条件:
  - 编译状态必须为 `success`
  - 许可证必须有效（排除 `none/error/unknown/rate_limited`）
  - `cscw_dialogue` 轮次在 `4~120`
- 构建结果:
  - 输入: 9000
  - 通过: 4709
  - 拒绝: 4291
  - 拒绝原因 Top3: `compilation_not_success`, `invalid_or_missing_license`, `dialogue_turns_out_of_range`
- 统计报告:
  - `reports/release_reports/release_v3_latest.md`
  - `reports/release_reports/release_v3_latest.json`

## 推荐使用顺序

1. 训练/实验优先: `v3_2026-02-27_latest_9k_cscw/release_v3_20260228`
2. 许可证审计追溯: `v2_2026-02-08_real_100percent_license_fix`
3. 方法学复盘: `v1_2026-02-05_legacy_8k_pipeline`
