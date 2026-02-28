# StreamVis 研究方案：实时对话流的意图成图

## 面向CSCW 2025/2026会议发表的研究数据集构建方案

---

## 摘要

本研究旨在构建一个大规模、高质量的"对话-图表"对齐数据集，用于训练实时对话流的意图成图模型。通过逆向工程方法，将现有图表还原为生成它们的原始对话场景，从而建立从自然语言到可视化表达的映射关系。该数据集将支持StreamVis系统的意图解码器训练，并为CSCW领域的对话驱动可视化研究提供基础资源。

**关键词**: 对话可视化、意图识别、协同工作、图表理解、逆向工程

---

## 1. 研究背景与动机

### 1.1 问题陈述

在计算机支持的协同工作（CSCW）场景中，可视化是促进团队理解和决策的关键工具。然而，当前的AI系统缺乏从自然对话流中自动识别可视化意图并生成相应图表的能力。现有方法主要依赖：

1. **显式命令触发**: 用户必须明确说出"画个图"等指令
2. **后处理生成**: 等待完整对话结束后统一处理
3. **模板匹配**: 基于有限模板生成固定类型图表

这些方法无法满足实时协同工作中"边说边出图"的需求。

### 1.2 研究目标

本研究的核心目标是：

> **构建能够从实时对话流中识别可视化意图并即时生成对应图表的AI系统**

具体目标包括：
1. 建立覆盖8-10类常用图表的大规模数据集（~8000条）
2. 提出并验证"视觉展示必要性"评估框架
3. 设计对话-图表对齐的分类学体系
4. 训练支持增量式图表生成的小模型

### 1.3 研究贡献

预期贡献：
1. **数据集贡献**: 首个大规模"对话-图表"对齐数据集，支持CSCW社区后续研究
2. **方法论贡献**: 图表逆向工程的标准化流程和质量评估框架
3. **技术创新**: 实时意图解码和增量图表生成技术
4. **应用价值**: 提升远程协作、会议记录、设计讨论等场景的效率

---

## 2. 数据集设计

### 2.1 数据Schema

每条数据记录包含以下核心模块：

```
record_id (UUID)
├── source (数据来源信息)
├── taxonomy (分类学标注)
│   ├── primary_category (主类型: flowchart/sequence_diagram/...)
│   ├── subcategory (子类型)
│   ├── structural_complexity (结构复杂度)
│   └── semantic_domain (语义领域)
├── visual_necessity (视觉必要性评估)
│   ├── overall_score (总分 0-10)
│   ├── dimensions (各维度评分)
│   │   ├── information_density
│   │   ├── spatial_relationship
│   │   ├── temporal_sequence
│   │   ├── comparative_analysis
│   │   └── cognitive_load_reduction
│   └── justification (评分理由)
├── conversation_context (对话场景)
│   ├── scenario_type (场景类型)
│   ├── participants (参与者信息)
│   └── communication_mode (通信模式)
├── chart_elements (图表元素统计)
├── intent_signals (意图信号)
├── reverse_engineering (逆向工程结果)
│   ├── reconstructed_dialogue (重建对话)
│   ├── turning_points (对话转折点)
│   └── incremental_evolution (渐进演化)
└── chart_representation (图表表示)
```

### 2.2 分类学设计

#### 2.2.1 图表类型分类

| 类别 | 代码 | 子类型 | 目标数量 | 优先级 | 数据来源 |
|------|------|--------|----------|--------|----------|
| 流程图 | flowchart | decision_flow, process_flow, system_flow | 1500 | ★★★★★ | GitHub + 合成 |
| 时序图 | sequence_diagram | system_interaction, business_process | 1200 | ★★★★★ | GitHub + 合成 |
| 思维导图 | mind_map | hierarchical, radial, fishbone | 1200 | ★★★★★ | GitHub + 合成 |
| 柱状图 | bar_chart | vertical, horizontal, grouped, stacked | 1000 | ★★★★☆ | 合成 + 网络 |
| 折线图 | line_chart | simple, multi-series, area | 1000 | ★★★★☆ | 合成 + 网络 |
| 甘特图 | gantt_chart | project_plan, milestone | 700 | ★★★★☆ | GitHub + 合成 |
| 网络图 | network_graph | hierarchical, force_directed | 700 | ★★★☆☆ | GitHub + 合成 |
| 饼图 | pie_chart | standard, donut, sunburst | 400 | ★★★☆☆ | 合成 |
| 矩阵/四象限 | matrix_quadrant | 2x2, SWOT, risk_matrix | 300 | ★★★☆☆ | 合成 |

#### 2.2.2 复杂度分级标准

| 级别 | 节点数 | 关系数 | 层级数 | 典型特征 |
|------|--------|--------|--------|----------|
| simple | 1-5 | 0-4 | 1 | 单一路径，无分支 |
| medium | 6-15 | 5-20 | 2-3 | 少量分支，简单层级 |
| complex | 16-30 | 21-50 | 3-5 | 多分支，交叉引用 |
| highly_complex | 30+ | 50+ | 5+ | 高度互联，多层嵌套 |

#### 2.2.3 语义领域

- **project_management**: 项目管理相关（进度、资源、风险）
- **software_engineering**: 软件工程（架构、流程、API）
- **business_analysis**: 商业分析（市场、财务、战略）
- **education**: 教育培训（课程、知识、技能）
- **research**: 学术研究（实验、数据、方法）
- **healthcare**: 医疗健康（流程、诊断、治疗）
- **finance**: 金融财务（投资、预算、报表）
- **manufacturing**: 制造业（生产、供应链、质检）
- **general**: 通用场景

### 2.3 视觉展示必要性评估框架

#### 2.3.1 理论基础

基于以下CSCW和信息可视化理论：

1. **认知负荷理论** (Sweller, 1988): 可视化如何降低工作记忆负担
2. **双重编码理论** (Paivio, 1986): 视觉和言语信息的协同处理
3. **空间表征理论** (Tversky, 2001): 空间布局对理解的影响
4. **协同认知理论** (Clark & Brennan, 1991): 共同 ground 的建立

#### 2.3.2 评估维度

| 维度 | 定义 | 测量标准 | 权重 |
|------|------|----------|------|
| information_density | 信息密度：纯文本表达的难度 | 元素数量 × 关系复杂度 | 0.20 |
| spatial_relationship | 空间关系：位置/连接关系的重要性 | 布局变化对理解的影响程度 | 0.20 |
| temporal_sequence | 时序性：步骤/时间顺序的重要性 | 顺序错误的严重性 | 0.15 |
| comparative_analysis | 比较分析：对比/分组需求强度 | 需要进行对比的元素对数 | 0.20 |
| cognitive_load_reduction | 认知负荷降低：相对纯文本的减负效果 | 信息检索时间节省估计 | 0.25 |

#### 2.3.3 评分方法

```
overall_score = Σ(dimension_i × weight_i) × adjustment_factor

adjustment_factor = 1 + 0.1 × (dimension_variance / max_variance)
```

其中 `dimension_variance` 是各维度分数的标准差，高方差表示多维度需求（如既需要时间顺序又需要空间关系）。

---

## 3. 数据收集方案

### 3.1 数据来源分布

| 来源 | 占比 | 优势 | 劣势 |
|------|------|------|------|
| GitHub仓库 | 45% | 真实场景、工程实践 | 分布不均、需要筛选 |
| 合成生成 | 45% | 可控、多样化 | 可能缺乏真实性 |
| 网络爬取 | 10% | 类型丰富 | 版权问题、质量参差 |

### 3.2 GitHub数据收集

#### 3.2.1 目标仓库选择标准

1. **活跃度高**: 最近6个月有更新
2. **star数**: 100+ stars（保证质量）
3. **图表丰富**: 包含README、docs、wiki等文档
4. **领域多样性**: 覆盖软件、商业、教育等领域

#### 3.2.2 搜索策略

使用GitHub Code Search API，针对不同图表类型的关键词：

```python
# 流程图
"flowchart TD" in:file extension:mmd
"flowchart LR" in:file extension:mmd

# 时序图
"sequenceDiagram" in:file extension:mmd

# PlantUML
"@startuml" in:file extension:puml

# Graphviz
"digraph" in:file extension:dot
```

#### 3.2.3 过滤条件

- 文件大小: 100 bytes - 50KB
- 排除测试文件、示例文件
- 排除明显错误的语法

### 3.3 合成数据生成

#### 3.3.1 生成策略

基于模板 + 随机填充 + 领域适配：

```
模板库 → 领域选择 → 占位符填充 → 变异添加 → 质量检查
```

#### 3.3.2 模板设计原则

1. **覆盖性**: 每种图表类型的常见模式
2. **真实性**: 基于真实场景设计
3. **多样性**: 不同复杂度、不同领域
4. **可扩展**: 易于添加新模板

### 3.4 预期收集计划

| 阶段 | 时间 | 目标 | 产出 |
|------|------|------|------|
| 阶段1 | Week 1-2 | GitHub数据收集 | ~3000张图表 |
| 阶段2 | Week 3-4 | 合成数据生成 | ~4000张图表 |
| 阶段3 | Week 5-6 | 网络数据补充 | ~1000张图表 |
| 阶段4 | Week 7-10 | 逆向工程处理 | 8000条完整记录 |
| 阶段5 | Week 11-12 | 质量验证与清洗 | ~7000条高质量记录 |

---

## 4. 逆向工程方法论

### 4.1 核心思想

逆向工程的核心假设：**每张图表都是在特定对话场景中为了解决特定沟通问题而产生的**。

因此，逆向工程的目标是：
1. 推断图表产生的原始对话场景
2. 重建对话的渐进式演化过程
3. 识别触发可视化需求的信号
4. 评估视觉展示的相对必要性

### 4.2 逆向工程Prompt设计

#### 4.2.1 角色设定

```
你是一个专业的协同工作可视化分析专家。
你的任务是对给定的图表进行深度逆向工程，
还原出该图表在真实工作场景中产生的完整对话上下文。
```

#### 4.2.2 分析框架

1. **结构分析**: 识别图表类型、复杂度、元素构成
2. **功能分析**: 推断图表要解决的沟通问题
3. **场景重建**: 基于图表特征推断对话场景
4. **对话模拟**: 生成真实的渐进式对话
5. **信号提取**: 识别显式和隐式意图信号

#### 4.2.3 输出规范

使用结构化JSON输出，包含所有schema字段。

### 4.3 质量控制机制

#### 4.3.1 自动化检查

| 检查项 | 阈值 | 说明 |
|--------|------|------|
| 必需字段完整性 | 100% | 所有必需字段必须存在 |
| 对话轮次 | ≥3轮 | 至少3轮对话 |
| 每轮长度 | ≥10字符 | 对话内容有意义 |
| 评分合理性 | 0-10范围 | 所有分数在有效范围 |
| 理由长度 | ≥50字符 | 评分有充分说明 |

#### 4.3.2 人工审核

- 抽样审核: 每批次随机抽取10%
- 专家复核: 对高分记录进行重点审核
- 反馈迭代: 根据审核结果调整prompt

### 4.4 渐进式演化建模

对于复杂图表，建模其可能的生成过程：

```
Stage 1: 骨架识别
  - 识别核心概念和主要关系
  - 建立基本框架

Stage 2: 主干添加
  - 填充主要流程或数据
  - 建立主要连接

Stage 3: 细节完善
  - 添加次要元素
  - 增加注释说明

Stage 4: 优化调整
  - 布局优化
  - 样式统一
```

---

## 5. 质量评估体系

### 5.1 评估维度

| 维度 | 指标 | 权重 | 评估方法 |
|------|------|------|----------|
| 完整性 | 字段完整率 | 0.20 | 自动检查 |
| 准确性 | 分类正确率 | 0.20 | 人工抽样 |
| 一致性 | 对话-图表匹配度 | 0.25 | 人工评估 |
| 多样性 | 类型覆盖熵 | 0.15 | 统计分析 |
| 真实性 | 对话自然度 | 0.20 | 人工评估 |

### 5.2 人工评估量表

#### 对话-图表匹配度 (1-5分)

- **5分**: 对话完全自然地导致该图表产生
- **4分**: 对话基本合理，有轻微不自然之处
- **3分**: 对话和图表有关联但略显牵强
- **2分**: 对话和图表关联性弱
- **1分**: 对话和图表明显不匹配

#### 对话自然度 (1-5分)

- **5分**: 完全像真实工作对话
- **4分**: 比较自然，偶有机器感
- **3分**: 能看出是生成的，但可用
- **2分**: 明显不自然
- **1分**: 完全不像人类对话

### 5.3 目标质量指标

| 指标 | 目标值 | 最低可接受值 |
|------|--------|--------------|
| 有效率（通过自动检查） | ≥90% | ≥80% |
| 分类准确率 | ≥95% | ≥85% |
| 对话-图表匹配度≥3分 | ≥80% | ≥70% |
| 对话自然度≥3分 | ≥85% | ≥75% |
| 类别覆盖完整度 | 100% | 100% |
| 重复率 | ≤5% | ≤10% |

---

## 6. 训练方案

### 6.1 模型选择

基于资源限制和研究需求，选择**轻量级模型**进行微调：

| 模型 | 参数规模 | 优势 | 适用阶段 |
|------|----------|------|----------|
| Qwen2.5-7B | 7B | 中文支持好、可部署 | 最终部署 |
| Llama-3.1-8B | 8B | 英文表现强、生态好 | 实验研究 |
| Mistral-7B | 7B | 推理效率高 | 快速迭代 |

### 6.2 训练任务设计

#### 任务1: 意图识别

输入: 对话上下文（最近N轮）
输出: 是否需要可视化的概率 + 推荐图表类型

```
[用户]: 我们需要讨论一下新功能的实现流程
[助手]: 好的，我们可以从需求分析开始

→ Intent: {trigger: true, category: flowchart, confidence: 0.85}
```

#### 任务2: 图表生成

输入: 完整对话
输出: 图表规范（Mermaid/JSON格式）

#### 任务3: 增量更新

输入: 新增对话 + 当前图表状态
输出: 图表增量（添加/修改/删除）

### 6.3 数据划分

| 划分 | 比例 | 用途 |
|------|------|------|
| 训练集 | 70% | 模型训练 |
| 验证集 | 15% | 超参数调优 |
| 测试集 | 15% | 最终评估 |

分层抽样确保各图表类型比例一致。

---

## 7. 伦理与隐私考量

### 7.1 数据来源合规

1. **GitHub数据**
   - 仅收集公开仓库
   - 遵守各仓库License
   - 记录数据来源便于追溯

2. **合成数据**
   - 不包含真实个人信息
   - 避免敏感领域（医疗、金融等）

3. **网络数据**
   - 遵守robots.txt
   - 优先使用CC许可内容

### 7.2 数据安全

- 数据集仅用于研究目的
- 不包含个人身份信息
- 发布时进行脱敏处理

---

## 8. 论文撰写计划

### 8.1 目标会议

**CSCW 2025/2026** (ACM Conference on Computer Supported Cooperative Work)

- 投稿截止日期: 2025年1月/5月（根据周期）
- 研究方向: HCI + CSCW + AI

### 8.2 论文结构

```
1. Introduction
   - 研究背景
   - 问题陈述
   - 研究贡献

2. Related Work
   - 对话系统与可视化
   - 意图识别研究
   - CSCW中的可视化

3. Dataset Design
   - 数据Schema设计
   - 分类学框架
   - 视觉必要性评估

4. Data Collection & Reverse Engineering
   - 数据收集方法
   - 逆向工程流程
   - 质量控制机制

5. Dataset Analysis
   - 统计分析
   - 多样性评估
   - 质量评估结果

6. Model Training & Evaluation
   - 训练任务设计
   - 实验设置
   - 结果分析

7. Discussion
   - 研究发现
   - 局限性
   - 未来工作

8. Conclusion
```

### 8.3 预期实验

| 实验 | 目的 | 预期结果 |
|------|------|----------|
| 意图识别准确率 | 验证分类效果 | >85% F1 |
| 图表生成质量 | 验证生成效果 | BLEU > 0.6 |
| 实时性测试 | 验证响应速度 | < 500ms |
| 用户研究 | 验证实用价值 | SUS > 70 |

---

## 9. 项目时间线

```
2024年11月
├── Week 1-2: 数据收集系统完善、GitHub数据收集
├── Week 3-4: 合成数据生成、网络数据收集

2024年12月
├── Week 1-2: 逆向工程处理（第一批）
├── Week 3-4: 质量验证、数据清洗、迭代优化

2025年1月
├── Week 1-2: 模型训练、实验评估
├── Week 3-4: 论文撰写（初稿）

2025年2月
├── Week 1-2: 论文完善、内部评审
└── Week 3-4: CSCW 2025 投稿

2025年3-4月
└── Rebuttal准备（如需要）

2025年5-8月
└── 补充实验、开源准备

2025年9月后
└── 开源发布、后续研究
```

---

## 10. 附录

### 附录A: 完整的Prompt模板

见 `reverse_engineering_prompt_template.md`

### 附录B: JSON Schema定义

见 `research_schema.json`

### 附录C: 数据处理脚本

1. `chart_data_collector.py` - 数据收集
2. `chart_dataset_processor.py` - 逆向工程处理
3. `quality_validator.py` - 质量验证

---

## 参考文献

[1] Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. Cognitive Science, 12(2), 257-285.

[2] Paivio, A. (1986). Mental representations: A dual coding approach. Oxford University Press.

[3] Tversky, B. (2001). Spatial schemas in depictions. In M. Gattis (Ed.), Spatial schemas and abstract thought (pp. 79-111). MIT Press.

[4] Clark, H. H., & Brennan, S. E. (1991). Grounding in communication. In L. B. Resnick, J. M. Levine, & S. D. Teasley (Eds.), Perspectives on socially shared cognition (pp. 127-149). APA.

[5] Heer, J., & Bostock, M. (2010). Crowdsourcing graphical perception: Using mechanical turk to assess visualization design. ACM CHI.

[6] Correll, M., Li, M., & Franconeri, S. (2023). The Science of Visual Data Communication. Nature Human Behaviour.

---

*最后更新: 2024年11月*
*版本: 1.0*
