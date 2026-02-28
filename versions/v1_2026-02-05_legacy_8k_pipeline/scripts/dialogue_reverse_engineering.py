#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话流逆向工程生成器

基于图表代码生成逼真的同步对话流，模拟两人逐步讨论并构建图表的过程。

核心方法 (参考DiagramAgent的Reverse Engineering):
1. 解析图表结构 (节点、边、层次)
2. 将结构分解为增量构建步骤
3. 为每个步骤生成对应的对话轮次
4. 应用言语行为理论标注

理论基础:
- 扩展的言语行为理论 (Visual Speech Act Theory)
- 认知负荷理论 (Cognitive Load Theory)
- 对话分析 (Conversation Analysis)
"""

import json
import random
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SpeechActType(Enum):
    """言语行为类型 - 基于视觉言语行为理论"""
    SEQUENTIAL = "sequential"      # 序列性行为: "首先...然后..."
    STRUCTURAL = "structural"      # 结构性行为: "包含...由...组成"
    CLASSIFICATION = "classification"  # 分类性行为: "分为...类型"
    CONTRASTIVE = "contrastive"    # 对比性行为: "相较于...优缺点"
    INFORM = "inform"              # 告知
    REQUEST = "request"            # 请求
    CONFIRM = "confirm"            # 确认
    CLARIFY = "clarify"            # 澄清


@dataclass
class DiagramElement:
    """图表元素"""
    id: str
    type: str  # 'node', 'edge', 'subgraph'
    label: str
    properties: Dict
    dependencies: List[str]  # 依赖的其他元素ID


@dataclass
class DialogueTurn:
    """对话轮次"""
    turn_id: int
    speaker: str  # 'Speaker_A', 'Speaker_B'
    utterance: str
    speech_act: SpeechActType
    diagram_elements_added: List[str]  # 本轮添加的图表元素
    timestamp_offset: int  # 相对于对话开始的时间偏移(秒)


class DiagramParser:
    """图表代码解析器"""

    def parse_mermaid(self, code: str) -> List[DiagramElement]:
        """解析Mermaid代码"""
        elements = []

        # 检测图表类型
        diagram_type = self._detect_mermaid_type(code)

        if diagram_type == 'flowchart':
            elements = self._parse_flowchart(code)
        elif diagram_type == 'sequence':
            elements = self._parse_sequence(code)
        elif diagram_type == 'class':
            elements = self._parse_class_diagram(code)
        elif diagram_type == 'mindmap':
            elements = self._parse_mindmap(code)
        else:
            elements = self._parse_generic(code)

        return elements

    def _detect_mermaid_type(self, code: str) -> str:
        """检测Mermaid图表类型"""
        if 'flowchart' in code or 'graph TD' in code or 'graph LR' in code:
            return 'flowchart'
        elif 'sequenceDiagram' in code:
            return 'sequence'
        elif 'classDiagram' in code:
            return 'class'
        elif 'mindmap' in code:
            return 'mindmap'
        elif 'gantt' in code:
            return 'gantt'
        elif 'erDiagram' in code:
            return 'er'
        return 'generic'

    def _parse_flowchart(self, code: str) -> List[DiagramElement]:
        """解析流程图"""
        elements = []

        # 解析节点: A[label] 或 A(label)
        node_pattern = r'(\w+)\s*[\[\(\{]\s*([^\]\)\}]+)\s*[\]\)\}]'
        nodes = re.findall(node_pattern, code)

        for i, (node_id, label) in enumerate(nodes):
            elem = DiagramElement(
                id=node_id,
                type='node',
                label=label.strip(),
                properties={'shape': self._detect_shape(code, node_id)},
                dependencies=[]
            )
            elements.append(elem)

        # 解析边: A --> B 或 A -->|label| B
        edge_pattern = r'(\w+)\s*--[\.]?\u003e\s*(?:\|([^|]+)\|)?\s*(\w+)'
        edges = re.findall(edge_pattern, code)

        for i, (from_node, label, to_node) in enumerate(edges):
            edge_id = f"edge_{i}"
            elem = DiagramElement(
                id=edge_id,
                type='edge',
                label=label.strip() if label else '',
                properties={'from': from_node, 'to': to_node},
                dependencies=[from_node, to_node]
            )
            elements.append(elem)

        return elements

    def _parse_sequence(self, code: str) -> List[DiagramElement]:
        """解析时序图"""
        elements = []

        # 解析参与者
        participant_pattern = r'participant\s+(\w+)\s+as\s+([^\n]+)'
        participants = re.findall(participant_pattern, code)

        for pid, label in participants:
            elem = DiagramElement(
                id=pid,
                type='participant',
                label=label.strip(),
                properties={},
                dependencies=[]
            )
            elements.append(elem)

        # 解析消息
        message_pattern = r'(\w+)(-?\u003e\u003e?)(\w+)\s*:\s*([^\n]+)'
        messages = re.findall(message_pattern, code)

        for i, (from_p, arrow, to_p, msg) in enumerate(messages):
            msg_id = f"msg_{i}"
            elem = DiagramElement(
                id=msg_id,
                type='message',
                label=msg.strip(),
                properties={'from': from_p, 'to': to_p, 'arrow': arrow},
                dependencies=[from_p, to_p]
            )
            elements.append(elem)

        return elements

    def _parse_class_diagram(self, code: str) -> List[DiagramElement]:
        """解析类图"""
        elements = []

        # 解析类定义
        class_pattern = r'class\s+(\w+)\s*\{([^}]*)\}'
        classes = re.findall(class_pattern, code, re.DOTALL)

        for class_name, content in classes:
            elem = DiagramElement(
                id=class_name,
                type='class',
                label=class_name,
                properties={'content': content.strip()},
                dependencies=[]
            )
            elements.append(elem)

        # 解析关系
        relation_pattern = r'(\w+)\s*(--\u003e|\<\|--|\.\.-\u003e|\.\.\|\u003e)\s*(\w+)'
        relations = re.findall(relation_pattern, code)

        for i, (from_c, rel, to_c) in enumerate(relations):
            rel_id = f"rel_{i}"
            elem = DiagramElement(
                id=rel_id,
                type='relationship',
                label=rel,
                properties={'from': from_c, 'to': to_c, 'type': rel},
                dependencies=[from_c, to_c]
            )
            elements.append(elem)

        return elements

    def _parse_mindmap(self, code: str) -> List[DiagramElement]:
        """解析思维导图"""
        elements = []

        lines = code.strip().split('\n')
        parent_stack = []

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            # 计算缩进级别
            indent = len(line) - len(line.lstrip())
            level = indent // 2

            # 提取标签
            label = line.strip().lstrip('root').strip('(){}[]').strip()

            # 调整父节点栈
            while len(parent_stack) > level:
                parent_stack.pop()

            elem_id = f"node_{i}"
            elem = DiagramElement(
                id=elem_id,
                type='mindmap_node',
                label=label,
                properties={'level': level},
                dependencies=[parent_stack[-1]] if parent_stack else []
            )
            elements.append(elem)
            parent_stack.append(elem_id)

        return elements

    def _parse_generic(self, code: str) -> List[DiagramElement]:
        """通用解析"""
        return [DiagramElement(
            id='root',
            type='generic',
            label='Generic Diagram',
            properties={'code': code},
            dependencies=[]
        )]

    def _detect_shape(self, code: str, node_id: str) -> str:
        """检测节点形状"""
        pattern = rf'{node_id}\s*(\[|\(|\{{|\[\()'
        match = re.search(pattern, code)
        if match:
            shape_map = {'[': 'rect', '(': 'circle', '{': 'diamond', '[(' : 'database'}
            return shape_map.get(match.group(1), 'rect')
        return 'rect'


class DialogueGenerator:
    """对话生成器"""

    # 对话模板库
    TEMPLATES = {
        SpeechActType.SEQUENTIAL: {
            'start': [
                "我们来设计一下这个流程，首先需要一个开始节点。",
                "首先，我们需要定义流程的起点。",
                "让我们从头开始，先确定入口点。"
            ],
            'continue': [
                "接下来，我们需要添加{element}。",
                "然后，我们应该考虑{element}。",
                "下一步是处理{element}。"
            ],
            'end': [
                "最后，流程到达{element}结束。",
                "最终，我们在{element}完成整个流程。"
            ]
        },
        SpeechActType.STRUCTURAL: {
            'introduce': [
                "这个系统主要由{element}组成。",
                "整体架构包含{element}这几个部分。",
                "从结构上看，我们有{element}。"
            ],
            'detail': [
                "{element}负责具体的功能实现。",
                "在{element}中，我们需要定义核心逻辑。"
            ]
        },
        SpeechActType.CLASSIFICATION: {
            'categorize': [
                "我们可以将{element}分为几个类型。",
                "{element}主要包含以下几类。"
            ]
        },
        SpeechActType.CONTRASTIVE: {
            'compare': [
                "相较于方案A，{element}有更好的性能。",
                "{element}和另一个方案相比，优势在于..."
            ]
        },
        SpeechActType.INFORM: {
            'general': [
                "我同意这个观点。",
                "这个设计看起来不错。",
                "我们需要确保这个逻辑是正确的。"
            ]
        },
        SpeechActType.REQUEST: {
            'ask': [
                "你能详细说明一下{element}吗？",
                "关于{element}，你有什么想法？",
                "我们应该如何处理{element}？"
            ]
        },
        SpeechActType.CONFIRM: {
            'agree': [
                "好的，那就按这个方案。",
                "明白了，{element}就这样设计。",
                "确认一下，{element}是正确的吧？"
            ]
        },
        SpeechActType.CLARIFY: {
            'explain': [
                "我的意思是{element}应该这样理解...",
                "让我澄清一下，{element}的作用是..."
            ]
        }
    }

    def __init__(self):
        self.parser = DiagramParser()
        self.speakers = ['Speaker_A', 'Speaker_B']

    def generate_dialogue(self, code: str, code_format: str = 'mermaid') -> List[DialogueTurn]:
        """
        生成对话流

        Args:
            code: 图表代码
            code_format: 代码格式

        Returns:
            对话轮次列表
        """
        # 1. 解析图表结构
        elements = self.parser.parse_mermaid(code)

        # 2. 将元素分组为增量构建步骤
        build_steps = self._group_into_steps(elements)

        # 3. 为每个步骤生成对话
        dialogue = []
        turn_id = 1

        for step_idx, step_elements in enumerate(build_steps):
            # 每个步骤生成2-4轮对话
            num_turns = random.randint(2, 4)

            for i in range(num_turns):
                speaker = self.speakers[turn_id % 2]

                # 确定言语行为类型
                if step_idx == 0 and i == 0:
                    speech_act = SpeechActType.SEQUENTIAL
                    template_key = 'start'
                elif step_idx == len(build_steps) - 1 and i == num_turns - 1:
                    speech_act = SpeechActType.SEQUENTIAL
                    template_key = 'end'
                else:
                    speech_act = self._select_speech_act(step_elements, i)
                    template_key = self._select_template_key(speech_act, i)

                # 生成话语
                utterance = self._generate_utterance(
                    speech_act, template_key, step_elements
                )

                turn = DialogueTurn(
                    turn_id=turn_id,
                    speaker=speaker,
                    utterance=utterance,
                    speech_act=speech_act,
                    diagram_elements_added=[e.id for e in step_elements] if i == num_turns - 1 else [],
                    timestamp_offset=turn_id * 15  # 每轮约15秒
                )

                dialogue.append(turn)
                turn_id += 1

        return dialogue

    def _group_into_steps(self, elements: List[DiagramElement]) -> List[List[DiagramElement]]:
        """将元素分组为增量构建步骤"""
        if not elements:
            return []

        # 按依赖关系排序
        sorted_elements = self._topological_sort(elements)

        # 分组: 每步1-3个元素
        steps = []
        current_step = []

        for elem in sorted_elements:
            current_step.append(elem)
            if len(current_step) >= random.randint(1, 3):
                steps.append(current_step)
                current_step = []

        if current_step:
            steps.append(current_step)

        return steps

    def _topological_sort(self, elements: List[DiagramElement]) -> List[DiagramElement]:
        """拓扑排序 (按依赖关系)"""
        # 简化的拓扑排序
        element_map = {e.id: e for e in elements}
        sorted_list = []
        visited = set()

        def visit(elem_id):
            if elem_id in visited:
                return
            visited.add(elem_id)

            elem = element_map.get(elem_id)
            if elem:
                for dep in elem.dependencies:
                    visit(dep)
                sorted_list.append(elem)

        for elem in elements:
            visit(elem.id)

        return sorted_list

    def _select_speech_act(self, elements: List[DiagramElement], turn_idx: int) -> SpeechActType:
        """选择合适的言语行为类型"""
        # 根据元素类型和轮次选择
        if turn_idx == 0:
            return random.choice([
                SpeechActType.STRUCTURAL,
                SpeechActType.CLASSIFICATION,
                SpeechActType.REQUEST
            ])
        elif turn_idx == 1:
            return random.choice([
                SpeechActType.INFORM,
                SpeechActType.CONFIRM,
                SpeechActType.CLARIFY
            ])
        else:
            return random.choice(list(SpeechActType))

    def _select_template_key(self, speech_act: SpeechActType, turn_idx: int) -> str:
        """选择模板键"""
        templates = self.TEMPLATES.get(speech_act, {})
        if not templates:
            return 'general'

        keys = list(templates.keys())
        return keys[turn_idx % len(keys)] if keys else 'general'

    def _generate_utterance(self, speech_act: SpeechActType, template_key: str,
                           elements: List[DiagramElement]) -> str:
        """生成话语"""
        templates = self.TEMPLATES.get(speech_act, {})
        template_list = templates.get(template_key, templates.get('general', ['好的。']))

        template = random.choice(template_list)

        # 替换占位符
        element_names = '、'.join([e.label for e in elements[:2]])
        utterance = template.format(element=element_names)

        return utterance

    def dialogue_to_json(self, dialogue: List[DialogueTurn]) -> List[Dict]:
        """转换为JSON格式"""
        return [
            {
                'turn_id': turn.turn_id,
                'speaker': turn.speaker,
                'utterance': turn.utterance,
                'speech_act': turn.speech_act.value,
                'diagram_elements_added': turn.diagram_elements_added,
                'timestamp_offset': turn.timestamp_offset
            }
            for turn in dialogue
        ]


class ConversationAnalyzer:
    """对话分析器"""

    def analyze(self, dialogue: List[DialogueTurn]) -> Dict:
        """分析对话特征"""
        stats = {
            'total_turns': len(dialogue),
            'speaker_distribution': {},
            'speech_act_distribution': {},
            'avg_turn_length': 0,
            'dialogue_duration': 0
        }

        total_length = 0

        for turn in dialogue:
            # 发言者分布
            stats['speaker_distribution'][turn.speaker] = \
                stats['speaker_distribution'].get(turn.speaker, 0) + 1

            # 言语行为分布
            act = turn.speech_act.value
            stats['speech_act_distribution'][act] = \
                stats['speech_act_distribution'].get(act, 0) + 1

            total_length += len(turn.utterance)

        if dialogue:
            stats['avg_turn_length'] = total_length / len(dialogue)
            stats['dialogue_duration'] = dialogue[-1].timestamp_offset

        return stats


def main():
    """测试对话生成器"""
    # 测试流程图
    test_code = """flowchart TD
    A[开始] --> B{用户已登录?}
    B -->|是| C[显示主页]
    B -->|否| D[跳转登录]
    D --> E[验证身份]
    E --> C
    C --> F[结束]"""

    generator = DialogueGenerator()
    dialogue = generator.generate_dialogue(test_code)

    print("生成的对话流:")
    print("=" * 60)
    for turn in dialogue:
        print(f"[{turn.turn_id}] {turn.speaker} ({turn.speech_act.value}):")
        print(f"    {turn.utterance}")
        if turn.diagram_elements_added:
            print(f"    [添加元素: {', '.join(turn.diagram_elements_added)}]")
        print()

    # 分析对话
    analyzer = ConversationAnalyzer()
    stats = analyzer.analyze(dialogue)

    print("\n对话统计:")
    print("=" * 60)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
