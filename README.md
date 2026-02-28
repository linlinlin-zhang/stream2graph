# Stream2Graph Versioned Archive

这个仓库是对 `/home/lin-server/pictures` 的版本化整理结果，目的是把不同阶段的数据集与脚本分开保存，便于追溯与复现实验。

## 版本目录

- `versions/v1_2026-02-05_legacy_8k_pipeline`
  - 8k 五阶段流水线时代产物（含 `01~05` 目录与早期脚本）
- `versions/v2_2026-02-08_real_100percent_license_fix`
  - 许可证修复与 high-quality 子集阶段
- `versions/v3_2026-02-27_latest_9k_cscw`
  - 最新版本（9k 数据 + CSCW 对话逆向工程）

详细说明见 [VERSION_INDEX.md](./VERSION_INDEX.md)。

## 最新可用发布集

- 发布路径: `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v3_20260228`
- 筛选规则:
  - `compilation_status == success`
  - 许可证有效（排除 `none/error/unknown/rate_limited`）
  - 存在 `cscw_dialogue` 且轮次在 `4~120`
- 当前规模: 4709 条
- 生成报告:
  - `reports/release_reports/release_v3_latest.md`
  - `reports/release_reports/release_v3_latest.json`

## 数据说明

- 本仓库是“按阶段归档”的工程仓库，不保证不同版本之间 schema 一致。
- 旧版本中的一些目录（例如 `v1` 的 `05_final`）主要是结构与索引保留，实际内容并不完整。
- 最新可用主线以 `v3_2026-02-27_latest_9k_cscw` 为准。

## 安全说明

- 原工程中的硬编码 GitHub Token 已全部替换为 `YOUR_GITHUB_TOKEN`。
- 若需运行采集脚本，请自行配置环境变量 `GITHUB_TOKEN`。

## 变更报告机制

- 已提供自动化脚本: `tools/generate_change_report.py`
- 已配置 Git hook: `.githooks/pre-commit`
- 本地已启用 `core.hooksPath=.githooks`，每次提交前会自动新增一份报告到:
  - `reports/change_reports/CHANGE_REPORT_*.md`
  - `reports/change_reports/CHANGE_REPORT_*.json`
- 新环境首次克隆后请执行:
  - `git config core.hooksPath .githooks`
