# Stream2Graph 增量图表更新方向项目方案

## 1. 方案摘要

本方案建议将 `Stream2Graph` 从“多轮对话生成最终 Mermaid 图表”的静态任务，重构为“面向实时对话前缀的增量图表状态跟踪与稳定更新”任务。

新的核心目标不再是只预测最终图，而是在对话进行过程中，系统持续接收前缀输入 `u1:t`，在每个时刻输出：

- 当前图状态 `G_t`
- 或相对于上一步的增量操作 `Δ_t`
- 并保证更新及时、结构正确、布局稳定、可渲染

这一路线有四个直接收益：

- 规避对正式用户实验的强依赖，论文主证据可由离线与实时客观指标支撑
- 与现有“静态 text-to-diagram generation/editing benchmark”形成明显区分
- 更贴合仓库中已经具备的实时管线、增量渲染与稳定性评测能力
- 为后续系统化微调、门卫模型、在线调度和真实产品原型提供统一叙事

一句话概括，新项目将围绕以下问题展开：

> 如何让系统在连续对话中逐步构建图表，并在保证结构正确的同时，尽量少改、尽量早改、稳定地改。

## 2. 为什么需要转向

### 2.1 原方向的主要风险

当前仓库的主任务仍然以“完整 CSCW 对话 -> 最终 Mermaid 图表”为主，例如：

- `tools/eval/dataset.py`
- `tools/finetune/prepare_qwen3_sft_dataset.py`

在这个设定下，核心评测仍然是最终图质量，实时部分更多像一个附属能力，而不是主任务本身。与此同时，当前 paper-facing 说明中仍将 `user study outcomes` 作为主要 rigor 组成部分之一，见：

- `docs/evaluation/PAPER_EXPERIMENT_MATRIX.md`

这会带来三个现实问题：

- 正式用户研究成本高，组织难度大，且非常消耗时间
- 如果用户实验规模不足，论文说服力反而可能受损
- 当前叙事与已有“benchmark + generation/editing + human evaluation”类工作相似度较高

### 2.2 与现有相关工作的重叠风险

你提到的 `From Words to Structured Visuals: A Benchmark and Framework for Text-to-Diagram Generation and Editing` 明确覆盖：

- 静态 diagram generation
- diagram coding
- diagram editing
- benchmark + framework + human evaluation

这类工作已经把“文本到图表生成/编辑”的静态问题定义得相当完整。如果继续沿这条路线推进，项目很容易落入以下位置：

- 任务定义接近
- 方法结构接近
- 数据集叙事接近
- 但缺少足够强的新增维度来支撑创新性

相比之下，“实时对话下的增量图表状态跟踪与稳定更新”引入了一个明确的新维度：

- 时间维度
- 前缀条件推理
- 在线更新策略
- 稳定布局约束
- 增量操作质量

这会把项目从“静态生成”转为“流式状态建模”，显著拉开与已有工作的边界。

## 3. 新方向的研究定位

### 3.1 推荐题目方向

中文题目可考虑：

- 面向实时对话的增量图表构建与稳定更新
- 基于前缀状态跟踪的实时图表增量更新系统
- 连续对话驱动的图表状态建模与增量渲染

英文题目可考虑：

- Stream2Graph: Incremental Diagram State Tracking and Stable Rendering from Streaming Dialogue
- Prefix-Conditioned Incremental Diagram Construction from Conversational Streams
- Real-Time Diagram State Tracking and Stable Updates for Conversational Diagram Building

### 3.2 核心研究问题

建议把研究问题明确为以下四个：

1. 给定持续增长的对话前缀，系统能否正确恢复当前图状态，而不是只预测最终图？
2. 系统能否在合适时机触发更新，而不是过早、过晚或频繁抖动？
3. 系统能否输出最小但充分的增量操作，而不是反复整体重写？
4. 系统能否在连续更新过程中维持较低闪烁和较强心理地图一致性？

### 3.3 主要贡献点

如果项目按本方案完成，论文的贡献可写成以下几类：

1. 任务贡献
   - 提出“流式对话前缀条件下的增量图表状态跟踪”任务
2. 数据贡献
   - 构建支持中间状态、增量操作和连续对话的 benchmark
3. 系统贡献
   - 提出算法层与模型层解耦的实时增量图表系统
4. 评测贡献
   - 建立同时衡量状态正确性、触发质量、延迟和稳定性的多维指标体系

## 4. 与现有仓库能力的衔接

这次转向不是推翻重来。仓库中已有多项关键能力可以直接复用。

### 4.1 可直接复用的能力

#### A. 实时管线骨架

- `versions/v3_2026-02-27_latest_9k_cscw/scripts/run_realtime_pipeline.py`
- `versions/v3_2026-02-27_latest_9k_cscw/scripts/streaming_intent_engine.py`

现有系统已经具备：

- transcript chunk 流式输入
- 在线 intent 推断
- update 触发
- renderer 调用
- 端到端事件记录

#### B. 增量渲染与稳定性统计

- `versions/v3_2026-02-27_latest_9k_cscw/scripts/incremental_renderer.py`

现有渲染器已经能产出：

- `flicker_index`
- `mean_displacement`
- `p95_displacement`
- `unchanged_max_drift`
- `mental_map_score`

这正是新方向最重要的系统层指标之一。

#### C. 实时评测框架

- `tools/eval/run_realtime_metrics.py`

现有实时评测已支持：

- `e2e_latency_p95_ms`
- `flicker_mean`
- `mental_map_mean`
- `runtime_over_transcript_ratio`
- `updates_emitted`

这意味着新 benchmark 的实时部分并不需要从零实现。

#### D. 数据再生产平台

- `tools/dialogue_regen/`
- `tools/dialogue_regen/build_dataset_version.py`

当前仓库已具备：

- 以 LLM 再生成对话
- 评分生成质量
- 将生成结果写回新版本数据集

这套产线非常适合扩展为“阶段分解 + 中间状态 + 连续对话”数据构建平台。

#### E. 微调数据准备链路

- `tools/finetune/prepare_qwen3_sft_dataset.py`
- `tools/finetune/train_qwen3_lora.py`

现有训练链路虽然目标还是“对话 -> 最终 Mermaid”，但已经完成了：

- split 读取
- chat-format SFT 数据导出
- LoRA / QLoRA 训练入口

改成“前缀 -> 当前状态”或“前缀 + 当前状态 -> 下一步操作”并不困难。

### 4.2 当前最需要替换的部分

以下部分需要重定义，而不是简单复用：

- `tools/eval/dataset.py` 中的任务定义
- 最终 Mermaid 作为唯一 gold 的数据表示
- 只看最终图质量的主评测目标
- 当前以完整对话为单位的一次性 SFT 样本

## 5. 新任务定义

建议把新项目拆成三个互相关联的任务。

### 5.1 任务 A: Prefix-to-State

输入：

- 截至时刻 `t` 的对话前缀 `u1:t`

输出：

- 当前图状态 `G_t`

这是最核心任务，因为它直接决定系统是否真正理解当前会话已经构建到哪里。

### 5.2 任务 B: State Delta Prediction

输入：

- 当前前缀 `u1:t`
- 上一步图状态 `G_{t-1}`

输出：

- 从 `G_{t-1}` 到 `G_t` 的最小增量操作 `Δ_t`

这比直接输出完整图更符合在线系统，也更容易控制更新幅度。

### 5.3 任务 C: Update Triggering / Gating

输入：

- 新到达的语音或文本 chunk
- 当前缓存窗口
- 当前图状态摘要

输出：

- `WAIT`
- `EMIT_UPDATE`
- `REPAIR`
- `ASK_CLARIFY`

这是小模型或门卫模块的主任务，用来决定是否需要调用较贵的大模型。

### 5.4 在线系统的统一形式

建议将在线推理统一表示为：

```text
prefix_t + state_{t-1} -> gate_t -> delta_t -> state_t -> render_t
```

## 6. 数据集设计

## 6.1 总体思路

建议从现有高质量 Mermaid 图表中选择约 `3000` 个最终图，基于结构复杂度将每个图分解为 `1-5` 个阶段，再为每个阶段生成对应的连续对话片段和图状态。

最终产出不止一个数据集，而是至少三层：

1. 最终图层
   - 原始最终 Mermaid / GraphIR
2. 阶段状态层
   - `G_1 ... G_k`
3. 对话前缀层
   - `u_1 ... u_t`
   - 每个前缀对齐到某个阶段状态

### 6.2 图类型范围

时间有限时，不建议一开始覆盖全部 Mermaid 类型。建议优先覆盖最适合增量构建的类型：

- `flowchart`
- `architecture`
- `sequence`
- `stateDiagram-v2`
- `er`
- `mindmap`

第二阶段再补：

- `class`
- `requirementDiagram`
- `gitGraph`

不建议在 v1 中优先投入：

- `pie`
- `gantt`
- `kanban`

这些类型虽然也能增量更新，但状态表示、结构对齐与局部更新逻辑不如前几类自然。

### 6.3 数据表示: 先统一为 GraphIR

不要把中间状态直接定义为 Mermaid 文本。建议新增一层统一中间表示 `GraphIR`。

推荐字段如下：

```json
{
  "graph_id": "sample_0001",
  "diagram_type": "flowchart",
  "nodes": [
    {
      "id": "n1",
      "label": "Start",
      "type": "process",
      "parent": null
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "n1",
      "target": "n2",
      "label": ""
    }
  ],
  "groups": [],
  "styles": [],
  "metadata": {}
}
```

这样做的原因是：

- GraphIR 更稳定，适合中间状态比较
- Mermaid 在中间态下有语法和排版噪声，不适合作为唯一 gold
- 不同图类可以共享相同评测接口

Mermaid 只作为：

- 可视化导出格式
- 编译检查对象
- 兼容现有平台的输出格式

### 6.4 阶段分解策略

每个最终图应先被分解成 `1-5` 个 macro stages：

- `Stage 1`: 初始最小结构
- `Stage 2`: 主干扩展
- `Stage 3`: 分支或子图补充
- `Stage 4`: 标签、条件、跨连接补充
- `Stage 5`: 修复与最终整理

在每个 macro stage 内，再记录更细的 micro operations：

- `add_node`
- `add_edge`
- `update_label`
- `add_group`
- `move_group`
- `repair_edge`
- `repair_label`

这样可以同时支持：

- 粗粒度 benchmark
- 细粒度 delta 学习

### 6.5 对话构造策略

一个最终图对应一段完整连续对话，而不是为每个阶段单独生成独立对话。

建议流程如下：

1. 从最终图得到阶段序列 `G_1 ... G_k`
2. 为每个阶段生成目标构建意图
3. 生成一段连续对话，其中每几轮推动一次阶段状态更新
4. 为每个 turn 标注其对齐的：
   - 所属 stage
   - 触发类型
   - 涉及元素
   - 是否 repair

### 6.6 数据集拆分

建议至少产出以下数据子集：

#### A. Benchmark 集

冻结，不参与再生成：

- `train`
- `validation`
- `test`

其中 `validation/test` 必须稳定冻结。

#### B. SFT-State 集

样本形式：

- `prefix -> current GraphIR`

#### C. SFT-Delta 集

样本形式：

- `prefix + previous GraphIR -> delta ops`

#### D. Gate 集

样本形式：

- `chunk window + state summary -> WAIT / EMIT / REPAIR / ASK`

### 6.7 数据质量控制

建议采用“多阶段代理集群 + 规则校验 + 小规模人工 spot check”的混合流程。

可以定义以下角色：

1. Decomposer Agent
   - 将最终图拆成阶段
2. Dialogue Planner Agent
   - 规划每阶段对话目的
3. Dialogue Writer Agent
   - 生成连续对话
4. State Aligner Agent
   - 将对话 turn 与状态更新对齐
5. Verifier Agent
   - 检查阶段单调性、结构合法性、元素一致性

但要注意：

- 代理集群用于离线数据生产是合理的
- 在线推理系统本身不应过度 agent 化，否则延迟和可复现性会失控

### 6.8 数据规模建议

建议采用“两阶段数据策略”：

#### Pilot 版

- `100-200` 个图
- 用于验证 schema、分解协议、指标和产线

#### 正式版

- `3000` 个图
- 作为 benchmark 主版本

不要一开始直接全量生产 3000 个样本，否则很容易在协议还不稳定时放大错误。

## 7. 系统架构设计

建议把系统分成两层。

### 7.1 算法层

算法层负责稳定、可控、可复现的在线行为。

主要模块：

1. Input Buffer
   - 管理实时 chunk 和前缀窗口
2. Boundary Detector
   - 判断当前是否形成可更新语义边界
3. State Store
   - 维护 `G_{t-1}` 和版本历史
4. Delta Executor
   - 将模型输出的操作应用到状态
5. Constraint Checker
   - 检查非法边、悬空节点、重复元素
6. Incremental Layout Engine
   - 负责局部布局与位置继承
7. Renderer
   - 导出 Mermaid / SVG / 前端可视化结构
8. Repair Manager
   - 在不一致时进行回滚或修复

### 7.2 模型层

模型层建议采用“小模型门卫 + 大模型主状态机”的结构。

#### 小模型

职责：

- 判断要不要更新
- 判断是否需要修复
- 过滤低价值 chunk
- 进行轻量意图或边界识别

优点：

- 延迟低
- 成本低
- 可频繁调用

#### 大模型

职责：

- 从前缀和当前状态生成高质量 `GraphIR` 或 `Δ_t`
- 处理复杂 repair
- 进行主状态推理

优点：

- 语义能力强
- 适合复杂结构与长程依赖

### 7.3 推荐在线推理流程

```text
chunk_t
  -> gate model
  -> if WAIT: hold
  -> if EMIT:
       prefix summary + state_{t-1}
       -> large model
       -> delta_t
       -> constraint checker
       -> state_t
       -> incremental renderer
  -> if REPAIR:
       repair path
```

## 8. Benchmark 设计

新 benchmark 不应只看最终图像不像，而应同时衡量结构、时机、稳定性和效率。

### 8.1 状态正确性指标

对每个状态 `G_t` 评测：

- node precision / recall / F1
- edge precision / recall / F1
- label F1
- group / subgraph match
- diagram type match
- GraphIR exact match
- Mermaid compile success

### 8.2 增量操作指标

对每个 `Δ_t` 评测：

- op precision / recall / F1
- minimality
  - 是否引入不必要操作
- over-update rate
  - 是否频繁整体重写
- repair necessity rate
  - 是否把正常更新错误地做成 repair

### 8.3 触发质量指标

对门卫模块评测：

- update trigger precision / recall / F1
- trigger latency
  - gold 可更新时刻到实际触发时刻的延迟
- premature update rate
- missed update rate
- unnecessary update rate

### 8.4 实时系统指标

现有仓库已经有基础，可继续扩展：

- end-to-end latency P50 / P95
- runtime over transcript ratio
- updates emitted
- average tokens per update
- average cost per session

### 8.5 稳定性指标

基于现有增量渲染器继续使用并扩展：

- flicker index
- mean displacement
- p95 displacement
- unchanged max drift
- mental map score

此外可新增：

- layout preservation score
- unchanged node retention rate
- local update ratio

### 8.6 会话级综合指标

建议新增 session-level 指标：

- Session Success Rate
  - 会话结束时最终图正确且 compile 成功
- Prefix Consistency Score
  - 中间状态是否单调接近最终图
- Stability-Adjusted Utility
  - 结构质量与稳定性综合分数

## 9. 实验设计

### 9.1 Baselines

至少应包括以下基线：

1. Final-only Baseline
   - 只在最后一次输出完整图
2. Heuristic Baseline
   - 复用现有传统实时管线
3. Large Model Direct State
   - 前缀直接输出完整 GraphIR
4. Large Model Delta
   - 前缀 + 上一状态输出 delta
5. Gate + Large Model
   - 小模型门卫 + 大模型

### 9.2 关键消融实验

建议做以下消融：

1. 无门卫 vs 有门卫
2. 输出完整状态 vs 输出增量操作
3. 无 constraint checker vs 有 checker
4. 无稳定布局约束 vs 有稳定布局约束
5. 不同阶段数分解策略
6. 不同图类型上的泛化差异

### 9.3 论文主表建议

建议至少拆成三张主表：

1. Prefix-State Quality
2. Trigger and Latency
3. Stability and Session Success

不要再把全部结果压成一张只看最终图质量的总表。

## 10. 微调方案

### 10.1 大模型微调目标

建议先做两条主线：

#### 路线 A: Prefix -> State

输入：

- 当前对话前缀

输出：

- 当前 `GraphIR` 或 Mermaid 中间态

优点：

- 简单直接
- 便于和静态基线比较

缺点：

- 冗余输出较多
- 不利于在线最小更新

#### 路线 B: Prefix + Previous State -> Delta

输入：

- 当前前缀
- 上一状态摘要

输出：

- 结构化 delta 操作

优点：

- 最贴近在线系统
- 更节省推理和渲染成本

缺点：

- 训练数据构造更复杂

建议顺序：

1. 先做路线 A，快速形成 baseline
2. 再做路线 B，体现系统创新性

### 10.2 小模型训练目标

小模型建议作为轻量分类器使用。

训练标签：

- `WAIT`
- `EMIT_UPDATE`
- `REPAIR`
- `ASK_CLARIFY`

可进一步增加：

- boundary type
- confidence bucket

### 10.3 训练样本格式

大模型 SFT 样本可以继续沿用现有 chat 格式：

```json
{
  "id": "sample_0001_t03",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "...prefix + state summary..."},
    {"role": "assistant", "content": "...GraphIR or delta JSON..."}
  ],
  "metadata": {}
}
```

这与当前 `tools/finetune/prepare_qwen3_sft_dataset.py` 的输出格式兼容。

### 10.4 模型选择建议

基于仓库当前经验，建议：

- 大模型 baseline:
  - `Qwen2.5-14B-Instruct`
  - `Qwen2.5-Coder-7B-Instruct`
- 小模型 gate:
  - 轻量 encoder 或小型 instruction 模型
  - 优先考虑成本与延迟，而不是极限能力

## 11. 工程落地方案

### 11.1 建议新增的目录

建议新增以下结构：

- `tools/incremental_dataset/`
  - 数据分解、状态对齐、质检、版本构建
- `tools/incremental_eval/`
  - state / delta / trigger / session 指标
- `tools/incremental_finetune/`
  - state 和 delta 数据导出
- `configs/incremental/`
  - benchmark、regen、finetune、ablation 配置

### 11.2 推荐新增脚本

建议第一阶段新增：

1. `tools/incremental_dataset/decompose_graph_stages.py`
2. `tools/incremental_dataset/generate_incremental_dialogues.py`
3. `tools/incremental_dataset/build_incremental_release.py`
4. `tools/incremental_eval/run_prefix_state_metrics.py`
5. `tools/incremental_eval/run_delta_metrics.py`
6. `tools/incremental_eval/run_trigger_metrics.py`
7. `tools/incremental_finetune/prepare_state_sft_dataset.py`
8. `tools/incremental_finetune/prepare_delta_sft_dataset.py`

### 11.3 与现有代码的衔接方式

建议复用而非复制的部分：

- 从 `tools/dialogue_regen/` 继承数据生成框架
- 从 `tools/eval/metrics.py` 继承结构匹配逻辑
- 从 `tools/eval/reporting.py` 继承汇总和切片逻辑
- 从 `versions/.../incremental_renderer.py` 继承稳定性度量
- 从 `tools/finetune/` 继承 SFT 数据与训练入口

## 12. 4-6 周执行路线

下面给出一个现实可执行的路线，默认以“先跑通、后扩量、再出结果”为原则。

### 第 1 周: 定义协议与 pilot

目标：

- 完成 `GraphIR` schema
- 完成 stage 分解协议
- 选出 `100-200` 个 pilot 图

交付：

- `GraphIR` schema 文档
- pilot 样本清单
- stage 分解示例

### 第 2 周: 数据产线 v1

目标：

- 打通最终图 -> 阶段状态 -> 连续对话 -> 前缀样本
- 建立规则校验和版本构建

交付：

- `pilot_incremental_release_v1`
- 数据质检报告

### 第 3 周: 评测平台 v1

目标：

- 跑通 state、delta、trigger、session 指标
- 接入现有稳定性和实时统计

交付：

- benchmark 评测脚本
- summary report 模板

### 第 4 周: 模型 baseline

目标：

- 跑通 `Prefix -> State` baseline
- 跑通 heuristic baseline

交付：

- baseline 结果
- 初步失败案例分析

### 第 5 周: 系统增强

目标：

- 加入 gate 模型
- 加入 `Prefix + Previous State -> Delta`
- 做关键消融

交付：

- gate ablation
- delta baseline

### 第 6 周: 扩量与论文叙事固化

目标：

- 从 pilot 扩到正式版
- 固化实验矩阵与论文图表

交付：

- 正式 benchmark 版本
- 论文方法图
- 实验主表草稿

## 13. 资源评估

### 13.1 时间

如果只做 pilot + 基线 + 评测闭环，4 周可落地。

如果要做到：

- 3000 图正式版
- state + delta + gate 三套任务
- 多模型比较

更合理的周期是 6 周左右。

### 13.2 计算

离线数据再生成的主要成本在 API 调用与校验，不在训练本身。

训练成本建议分层控制：

- 先用小样本 smoke 验证
- 再做 7B / 14B 级别 SFT
- 只有在指标闭环成立后再考虑更大模型

### 13.3 人力

最小可行团队分工：

1. 数据协议与产线
2. 评测与报告
3. 训练与系统集成

如果只有 1-2 人，也能做，但必须严格控制首版 scope。

## 14. 风险与应对

### 风险 1: 数据生成质量不稳定

应对：

- 先 pilot
- 多阶段规则校验
- 少量人工 spot check

### 风险 2: 中间状态定义含糊

应对：

- 先定义 `GraphIR`
- 再定义 Mermaid 导出
- 避免直接拿 Mermaid 中间态做唯一真值

### 风险 3: 评测过多过散

应对：

- 主指标只保留四类：
  - state quality
  - trigger quality
  - latency
  - stability

### 风险 4: scope 膨胀

应对：

- v1 只做 4-6 类图
- v1 只做 pilot 规模
- 先做 `Prefix -> State`
- 再做 delta 和 gate

## 15. 最终建议

本项目最值得做的，不是继续把“最终图生成”做得更像已有工作，而是把 `Stream2Graph` 明确重构为：

> 一个针对实时对话前缀、面向增量图表状态跟踪、支持稳定渲染与在线调度的系统与 benchmark。

这条路线的最大优势是：

- 创新点更集中
- 工程基础更匹配
- 不依赖正式用户实验
- 数据、系统、训练、评测可以形成闭环

建议的执行策略是：

1. 先做 pilot，不要直接全量开工
2. 先做 state baseline，再做 delta
3. 先复用现有 realtime 和 renderer 能力，再扩展评测
4. 用一份正式 benchmark 叙事统一数据、模型、系统和论文

## 16. 外部参考

以下工作主要用于定位新方向，而不是直接复用其任务定义：

- Wei et al., *From Words to Structured Visuals: A Benchmark and Framework for Text-to-Diagram Generation and Editing*
  - `https://arxiv.org/html/2411.11916v1`
  - 代表“静态 generation / coding / editing + benchmark + human evaluation”路线

- 图表与流程图相关理解类 benchmark
  - `ChartQA`
  - `FlowVQA`
  - 主要说明现有资源大多集中在静态理解，而不是连续增量构建

- 仓库内直接相关文档与代码
  - `docs/evaluation/PAPER_EXPERIMENT_MATRIX.md`
  - `tools/eval/dataset.py`
  - `tools/dialogue_regen/`
  - `tools/finetune/`
  - `versions/v3_2026-02-27_latest_9k_cscw/scripts/incremental_renderer.py`
  - `tools/eval/run_realtime_metrics.py`
