# StreamVis 研究项目汇总

## 项目概述

本项目为 **CSCW 2025/2026** 会议投稿准备，目标是构建一个大规模、高质量的"对话-图表"对齐数据集，用于训练实时对话流的意图成图模型。

---

## 已创建的文档和脚本

### 核心文档

| 文件名 | 说明 | 用途 |
|--------|------|------|
| `RESEARCH_PROPOSAL.md` | 完整研究方案 | 论文基础、项目规划 |
| `README.md` | 项目使用说明 | 快速上手、API参考 |
| `PROJECT_SUMMARY.md` | 本文件 | 项目总览 |

### 技术规范

| 文件名 | 说明 | 用途 |
|--------|------|------|
| `research_schema.json` | 数据Schema定义 | 数据验证、接口规范 |
| `reverse_engineering_prompt_template.md` | 逆向工程Prompt | LLM调用模板 |

### Python脚本

| 文件名 | 功能 | 使用场景 |
|--------|------|----------|
| `run_pipeline.py` | 一键流水线 | 完整数据构建流程 |
| `chart_data_collector.py` | 数据收集 | GitHub/合成数据获取 |
| `chart_dataset_processor.py` | 逆向工程处理 | LLM API调用处理 |
| `quality_validator.py` | 质量验证 | 数据验证分析 |
| `prepare_training_data.py` | 训练数据准备 | 格式转换、任务拆分 |

### 现有工具（继承）

| 文件名 | 功能 |
|--------|------|
| `download_diagram_dataset.py` | GitHub图表批量下载 |
| `github_diagram_downloader.py` | 基础GitHub下载器 |
| `synthetic_diagram_generator.py` | 合成图表生成 |

---

## 数据集设计

### 分类学体系

#### 9类图表（共8000张）

```
高优先级 (★★★★★)
├── 流程图 (Flowchart)          1500张
├── 时序图 (Sequence Diagram)   1200张
└── 思维导图 (Mind Map)         1200张

中优先级 (★★★★☆)
├── 柱状图 (Bar Chart)          1000张
├── 折线图 (Line Chart)         1000张
├── 甘特图 (Gantt Chart)         700张
└── 网络图 (Network Graph)       700张

低优先级 (★★★☆☆)
├── 饼图 (Pie Chart)             400张
└── 矩阵/四象限 (Matrix)         300张
```

### 数据Schema核心字段

```
record
├── taxonomy (分类学)
│   ├── primary_category: 主类型
│   ├── subcategory: 子类型
│   ├── structural_complexity: 复杂度
│   └── semantic_domain: 语义领域
│
├── visual_necessity (视觉必要性)
│   ├── overall_score: 总分(0-10)
│   ├── dimensions: 五维度评分
│   └── justification: 理由说明
│
├── reverse_engineering (逆向工程)
│   ├── reconstructed_dialogue: 重建对话
│   ├── turning_points: 对话转折点
│   └── incremental_evolution: 渐进演化
│
└── intent_signals (意图信号)
    ├── explicit_triggers: 显式触发词
    ├── implicit_signals: 隐式信号
    └── contextual_clues: 上下文线索
```

---

## 使用流程

### 1. 环境准备

```bash
# 安装依赖
pip install aiohttp aiofiles python-dotenv

# 配置环境变量
export KIMI_API_KEY="your-kimi-api-key"
export GITHUB_TOKEN="your-github-token"  # 可选
```

### 2. 完整流水线（推荐）

```bash
# 运行所有阶段
python run_pipeline.py --api-key YOUR_KEY

# 或分阶段运行
python run_pipeline.py --stage collection        # 仅数据收集
python run_pipeline.py --stage processing        # 仅逆向工程
python run_pipeline.py --stage validation        # 仅质量验证
```

### 3. 分步执行（灵活控制）

#### 步骤1: 数据收集

```bash
python chart_data_collector.py
```

输出: `./dataset_raw/` 目录下的图表文件

#### 步骤2: 逆向工程

```bash
python chart_dataset_processor.py
```

输出: `./processed_dataset/` 目录下的JSON记录

#### 步骤3: 质量验证

```bash
python quality_validator.py
```

输出: 验证报告和分析文件

#### 步骤4: 训练数据准备

```bash
python prepare_training_data.py --format jsonl
```

输出: `./training_data/` 目录下的训练数据

---

## 训练任务

### 任务1: 意图识别

**目标**: 从对话中识别是否需要可视化

**输入**:
```
[PM] 我们需要梳理一下登录流程
[Dev] 好的，包括异常处理吗？
```

**输出**:
```json
{
  "trigger": true,
  "category": "flowchart",
  "confidence": 0.85
}
```

### 任务2: 图表生成

**目标**: 根据对话生成图表规范

**输入**: 完整对话文本

**输出**: Mermaid/JSON格式的图表规范

### 任务3: 图表分类

**目标**: 自动分类图表类型

**输入**: 图表规范/描述

**输出**: 分类标签（类型、复杂度、领域）

### 任务4: 视觉必要性预测

**目标**: 预测使用图表的必要性

**输入**: 对话上下文

**输出**: 必要性分数和理由

### 任务5: 增量式生成

**目标**: 支持渐进式图表更新

**输入**: 新增对话 + 当前图表状态

**输出**: 图表增量（添加/修改/删除）

---

## 质量目标

| 指标 | 目标值 | 最低值 |
|------|--------|--------|
| 有效率 | ≥90% | ≥80% |
| 分类准确率 | ≥95% | ≥85% |
| 对话-图表匹配度 | ≥80% | ≥70% |
| 对话自然度 | ≥85% | ≥75% |
| 重复率 | ≤5% | ≤10% |

---

## 研究创新点

### 1. 方法论创新

- **逆向工程方法**: 从图表反推对话场景
- **视觉必要性框架**: 量化图表相对于文本的价值
- **渐进式建模**: 模拟图表的动态生成过程

### 2. 技术创新

- **实时意图解码**: 支持流式对话的实时分析
- **增量图表生成**: 支持边对话边更新图表
- **多模态对齐**: 自然语言与可视化语言的映射

### 3. 应用价值

- **远程协作**: 提升视频会议效率
- **设计讨论**: 辅助设计思维的表达
- **知识分享**: 降低技术文档的理解门槛

---

## 论文规划

### 目标会议

**CSCW 2025/2026** (ACM Conference on Computer Supported Cooperative Work)

- 截稿时间: 2025年1月/5月
- 研究方向: HCI + CSCW + AI

### 论文结构

```
1. Introduction
2. Related Work
3. Dataset Design
   - Schema设计
   - 分类学框架
   - 视觉必要性评估
4. Data Collection & Reverse Engineering
5. Dataset Analysis
6. Model Training & Evaluation
7. Discussion
8. Conclusion
```

---

## 项目时间线

```
2024年11月
├── Week 1-2: 数据收集系统完善
├── Week 3-4: 合成数据生成

2024年12月
├── Week 1-2: 逆向工程处理
├── Week 3-4: 质量验证迭代

2025年1月
├── Week 1-2: 模型训练实验
└── Week 3-4: 论文初稿撰写

2025年2月
├── Week 1-2: 论文完善评审
└── Week 3-4: CSCW投稿
```

---

## 快速开始示例

### 单文件测试

```python
import asyncio
from chart_dataset_processor import ChartDatasetProcessor

async def test():
    processor = ChartDatasetProcessor(
        api_key="your-api-key",
        api_provider="kimi",
        output_dir="./test_output"
    )

    from pathlib import Path
    result = await processor.process_chart(
        Path("./test_dataset/mermaid/example.mmd")
    )

    print(f"记录ID: {result.record_id}")
    print(f"分类: {result.taxonomy.primary_category}")
    print(f"视觉必要性: {result.visual_necessity.overall_score}")
    print(f"对话轮数: {len(result.reverse_engineering.reconstructed_dialogue)}")

asyncio.run(test())
```

### 批量处理

```python
import asyncio
from chart_dataset_processor import ChartDatasetProcessor
from pathlib import Path

async def batch_process():
    processor = ChartDatasetProcessor(
        api_key="your-api-key",
        output_dir="./output"
    )

    chart_files = list(Path("./dataset_raw").rglob("*.mmd"))

    results = await processor.process_batch(
        chart_files[:100],  # 先处理100个
        max_concurrent=5
    )

    print(f"成功: {sum(1 for r in results if r is not None)}")

asyncio.run(batch_process())
```

---

## 目录结构预期

```
pictures/
├── README.md                          # 项目说明
├── RESEARCH_PROPOSAL.md              # 研究方案
├── PROJECT_SUMMARY.md                # 本文件
│
├── research_schema.json               # 数据Schema
├── reverse_engineering_prompt_template.md
│
├── run_pipeline.py                    # 一键流水线
├── chart_data_collector.py           # 数据收集
├── chart_dataset_processor.py        # 逆向工程
├── quality_validator.py              # 质量验证
├── prepare_training_data.py          # 训练数据准备
│
├── dataset_raw/                       # 原始图表数据
│   ├── flowchart/
│   ├── sequence_diagram/
│   └── ...
│
├── processed_dataset/                 # 处理后数据
│   ├── flowchart/
│   ├── validation_report.json
│   └── diversity_analysis.json
│
└── training_data/                     # 训练数据
    ├── intent_detection/
    ├── chart_generation/
    └── ...
```

---

## 注意事项

### API使用

1. **速率限制**: 各API提供商有不同的速率限制，请遵守
2. **成本控制**: 处理8000条数据预计需要一定的API费用
3. **错误处理**: 脚本包含重试机制，但仍可能因网络/API问题失败

### 数据安全

1. **隐私保护**: 数据集中不包含个人身份信息
2. **许可证**: 遵守各数据来源的许可证要求
3. **发布**: 公开发布前进行脱敏处理

### 质量控制

1. **人工审核**: 建议对高价值样本进行人工审核
2. **迭代优化**: 根据质量报告调整prompt和处理流程
3. **多样性**: 确保各领域、各复杂度等级都有足够覆盖

---

## 联系方式

如有问题或建议，欢迎提交Issue。

---

*最后更新: 2024年11月*
*版本: 1.0*
*目标会议: CSCW 2025/2026*
