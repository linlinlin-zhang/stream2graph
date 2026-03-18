# Stream2Graph 增量数据集构建系统技术蓝图

## 1. 文档目的

这份文档用于把新的增量数据集方向收敛成一个可以直接开工的工程系统，而不只是研究设想。

目标不是立刻把 `3000` 份完整样本一次性全部生产完，而是先把“真正开跑前必须完成的全部基础设施”搭好，并且让系统具备以下能力：

- 能从最新 `v7` 数据集中稳定筛选出 `3000` 个结构复杂度分布合理的图表
- 能把最终图表代码解析为统一 `GraphIR`
- 能基于算法把每个图拆成 `1-5` 个单调递进的阶段状态
- 能用 MiniMax `MiniMax-M2.7` 构建真实可运行的多 agent 离线生产流水线
- 能在 Token Plan 配额受限时自动停下、保存断点、等待后续续跑
- 能把结构层、agent 层、校验层和导出层连成一个完整闭环

## 2. 新系统的原则

### 2.1 结构真值优先

新的数据集以现有高质量图表代码为唯一结构真值来源。

- 保留现有数据集中的 `code`
- 不再把旧 `cscw_dialogue` 作为新 benchmark 的核心 gold
- 中间状态和阶段边界先由算法决定，再允许 agent 在语言层补充连续对话

这意味着：

- `GraphIR` 是主真值
- `stage states` 是第二层真值
- `continuous dialogue` 是围绕上述真值构建的辅助监督层

### 2.2 算法负责可验证，Agent 负责可读与可连续

算法层负责：

- Mermaid 解析
- 复杂度评估
- 三千样本筛选
- 阶段拆解
- 单调性检查
- delta 生成
- 规则校验

Agent 层负责：

- 阶段语义卡片生成
- 连续对话生成
- turn 到 stage 的对齐
- 对话一致性检查与修补

### 2.3 真正的“多 agent”

这里的多 agent 不是为了把系统做复杂，而是为了把离线生产过程拆成可控角色：

1. `StagePlanner`
   - 阅读算法拆解结果
   - 为每个阶段生成语义目标与语言约束
2. `DialogueWriter`
   - 基于全部阶段一次性生成连续对话
3. `TurnAligner`
   - 将 turn 与阶段边界、触发点重新对齐
4. `Verifier`
   - 检查是否越界引用未来元素、是否漏掉关键结构、是否连续

所有 agent 都统一使用 `MiniMax-M2.7`。

## 3. 数据源与选择标准

### 3.1 源数据

第一版默认使用当前仓库中的最新正式数据集版本：

- `versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v7_kimi_k25_fullregen_strict_20260313`

### 3.2 目标图类

第一版优先支持以下图类：

- `flowchart`
- `architecture`
- `sequence`
- `statediagram`
- `er`
- `mindmap`

原因是这些类型最适合做“阶段化增量构建”，并且更容易建立统一 `GraphIR`。

### 3.3 三千样本筛选标准

系统不是简单随机抽样，而是按以下标准筛：

1. 图类平衡
   - 尽量让六类核心图都被覆盖
2. 复杂度平衡
   - 按复杂度分成 `5` 桶，避免全部集中在简单图或超复杂图
3. 质量优先
   - 优先保留 `compile success`
   - 优先保留非增强样本，再补增强样本
4. 稳定可复现
   - 选择算法必须是确定性的，同一配置重复运行得到同一批结果

### 3.4 复杂度指标

默认复杂度分由以下因素加权：

- 节点数
- 边数
- group / subgraph 数
- 分支节点数
- 标签数
- 源代码非空行数

复杂度分还会映射到推荐阶段数：

- `1` 阶段：极简图
- `2` 阶段：简单图
- `3` 阶段：中等复杂图
- `4` 阶段：复杂图
- `5` 阶段：高复杂图

## 4. 系统总架构

系统分为三层：

### 4.1 Deterministic Core

代码目录：

- `tools/incremental_dataset/`

职责：

- 加载源数据
- Mermaid 解析为 `GraphIR`
- 复杂度分析
- 三千样本选择
- 阶段拆解
- 阶段状态导出

### 4.2 Agent Orchestration

职责：

- 组织 `StagePlanner / DialogueWriter / TurnAligner / Verifier`
- 统一调用 `MiniMax-M2.7`
- 控制请求间隔、配额、重试、缓存、断点续跑

### 4.3 Dataset Builder

职责：

- 把结构层输出和 agent 层输出合并为最终样本
- 维护每个样本的状态机
- 导出中间产物与最终产物

## 5. GraphIR 与阶段状态

### 5.1 GraphIR

每个图统一转换为：

```json
{
  "graph_id": "sample_0001",
  "diagram_type": "flowchart",
  "nodes": [],
  "edges": [],
  "groups": [],
  "styles": [],
  "metadata": {}
}
```

`GraphIR` 的作用：

- 作为阶段状态的统一结构
- 作为 delta 的基础
- 作为训练与评测时的结构 gold

### 5.2 阶段状态

每个样本都会被拆成：

- `G_1 ... G_k`
- `Δ_1 ... Δ_k`
- `k ∈ [1, 5]`

每个阶段必须满足：

- 单调递进
- 不删除前序已建立核心结构
- 当前阶段的边只能依赖当前或更早出现的节点

### 5.3 Preview Mermaid

阶段数据里会额外导出一个 `preview_mermaid`，只用于人工检查和快速浏览，不作为结构 gold。

## 6. MiniMax Agent 集群设计

### 6.1 模型与接口

统一使用：

- 模型：`MiniMax-M2.7`
- OpenAI 兼容 base URL：`https://api.minimaxi.com/v1`
- chat completions endpoint：`https://api.minimaxi.com/v1/chat/completions`

官方文档：

- OpenAI API 兼容: <https://platform.minimaxi.com/docs/api-reference/text-openai-api>
- Mini-Agent: <https://platform.minimaxi.com/docs/solutions/mini-agent>

### 6.2 Token Plan 约束

系统需要兼容 Token Plan 的动态五小时窗口限制，因此 agent orchestration 必须支持：

- 固定窗口调用计数
- 配额查询
- 到限自动停机
- checkpoint 保存
- 五小时后继续执行

官方文档：

- Best practices: <https://platform.minimaxi.com/docs/token-plan/best-practices>
- FAQ / remains 接口说明: <https://platform.minimaxi.com/docs/coding-plan/faq>

### 6.3 配额策略

默认策略：

- 维护本地调用窗口计数
- 定期查询 `coding_plan/remains`
- 剩余额度低于阈值时停止
- 将未完成任务保留在队列中

### 6.4 断点续跑

每个样本的 agent 输出都按样本单独落盘：

- 已完成步骤不重复生成
- 失败步骤可单独重试
- 达到配额后下次继续未完成样本

## 7. 输出目录

默认运行目录：

- `data/incremental_dataset/runs/<run_name>/`

结构建议：

- `selection/`
  - `all_profiles.jsonl`
  - `selection_manifest.json`
  - `selected_sample_ids.json`
  - `splits/`
- `structure/`
  - `samples/<sample_id>.json`
  - `build_report.json`
- `agent_cluster/`
  - `sample_outputs/<sample_id>.json`
  - `run_report.json`
- `events.jsonl`
- `run_manifest.json`

## 8. 配置原则

跟仓库同步的配置只保留示例文件，不保存真实 key。

受 git 管理的文件：

- `configs/incremental_dataset/*.example.json`

本地私有配置：

- `configs/incremental_dataset/*.local.json`
- 或直接使用环境变量 `MINIMAX_API_KEY`

## 9. 开工顺序

建议按以下顺序执行：

1. 先跑全量 profile 与三千样本选择
2. 再跑三千样本的结构拆解
3. 再启用 MiniMax agent 集群做语言层生产
4. 每批完成后进行中间检查和 git 提交

## 10. 第一版完成标准

只要以下内容全部具备，就算“真正开始构建新数据集之前的准备工作已经完成”：

1. 有正式技术文档和运行方案
2. 有可运行的三千样本筛选器
3. 有可运行的 Mermaid -> GraphIR -> Stages 算法管线
4. 有 MiniMax-M2.7 agent orchestration
5. 有配额控制、断点续跑、缓存和日志
6. 有一条 `run_full_build` 入口脚本能把各层串起来

## 11. 当前执行决策

本轮实现遵循下面的工程决策：

- 结构层今天直接全量落地并开始运行
- agent 集群今天搭成真实可跑版本
- 真实 key 不进入 git
- 输出产物默认写入被忽略的 `data/` 目录
- 提交时按“文档与协议 / 算法层 / agent 层 / 配置与运行结果”分批提交
