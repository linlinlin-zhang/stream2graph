# Stream2Graph Dataset

## 数据集概述

Stream2Graph 是一个面向"实时同步话语可视化"研究的大规模数据集，包含 {对话流, 演进图表} 配对。

## 构建方法

采用逆向工程 (Reverse Engineering) 方法，参照 DiagramAgent (CVPR 2025) 的数据集构建流程：
1. 从GitHub/HuggingFace收集高质量图表代码
2. 编译验证确保代码质量
3. 使用GPT-4o逆向生成自然会议对话
4. 构建增量演进步骤

## 理论基础

基于《实时成图研究想法》中的视觉言语行为理论：
- Sequential → 流程图/时序图
- Structural → 架构图/类图
- Classification → 思维导图/树状图
- Contrastive → 比较矩阵/表格
- Relational → ER图

## 数据统计

- **总样本数**: 0
- **版本**: 2.0

### 数据划分

#### TRAIN
- 样本数: 0
- 平均质量分数: 0.000
- 图表类型分布: {}

#### VALIDATION
- 样本数: 0
- 平均质量分数: 0.000
- 图表类型分布: {}

#### TEST
- 样本数: 0
- 平均质量分数: 0.000
- 图表类型分布: {}

