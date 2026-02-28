#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSCW-Grade Dialogue Reverse Engineering Engine
基于 CSCW 理论的协作对话逆向生成器

Theoretical Frameworks:
1. Grounding in Communication (Clark & Brennan, 1991)
2. Asymmetric Collaboration (Domain Expert vs. Technical Editor)
3. Conversational Repair and Iterative Sensemaking
"""

import json
import random
import re
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

class Role(Enum):
    EXPERT = "Domain_Expert"   # Focuses on semantics and business logic
    EDITOR = "Diagram_Editor"  # Focuses on structure, syntax, and execution

class ActionType(Enum):
    PROPOSE = "propose"        # Expert proposes a new concept
    CLARIFY = "clarify"        # Editor clarifies technical implementation
    CONFIRM = "confirm"        # Expert confirms the Editor's understanding (Grounding)
    REPAIR = "repair"          # Simulated self-correction or modification
    EXECUTE = "execute"        # Editor outputs the code change

@dataclass
class DiagramElement:
    id: str
    type: str
    label: str
    properties: Dict
    dependencies: List[str]

@dataclass
class Turn:
    turn_id: int
    role: str
    action_type: str
    utterance: str
    elements_involved: List[str]
    is_repair: bool

class CSCWDialogueGenerator:
    def __init__(self):
        # 领域专家的表述库 (更偏向业务)
        self.expert_proposals = [
            "我们需要加一个处理 {label} 的环节。",
            "接下来是关于 {label} 的逻辑。",
            "然后，流程会走到 {label}。",
            "这里必须包含 {label} 这一块。",
            "用户在这里会遇到 {label} 的分支。"
        ]
        self.expert_repairs = [
            "等等，我重新想了一下，应该是 {label} 才对。",
            "不，其实叫 {label} 会更准确一点。",
            "抱歉，稍微改一下，把刚才那个改成 {label}。"
        ]
        
        # 制图者的表述库 (更偏向结构和确认)
        self.editor_clarifications = [
            "好的，我把它画成一个{shape}，名字叫 '{label}'，对吧？",
            "明白，所以它是承接上一步的，内容是 '{label}'？",
            "收到。这是不是一个判断条件？我暂时写成 '{label}'。",
            "我把它加进去了，标签显示为 '{label}'，你看看合适吗？"
        ]
        
    def _get_shape_desc(self, element: DiagramElement) -> str:
        shape_map = {'rect': '矩形框', 'circle': '圆形节点', 'diamond': '菱形判断框', 'database': '数据库圆柱体'}
        return shape_map.get(element.properties.get('shape', 'rect'), '普通节点')

    def generate_grounded_dialogue(self, elements: List[DiagramElement]) -> List[Turn]:
        """生成基于 Grounding 理论的多轮交互"""
        dialogue = []
        turn_idx = 1
        
        # 将元素分组，每次处理 1-2 个，模拟人的认知负荷
        chunks = [elements[i:i + 2] for i in range(0, len(elements), 2)]
        
        for chunk in chunks:
            label_text = " 和 ".join([e.label for e in chunk if e.label])
            if not label_text: label_text = "这个连接"
            
            # 1. Expert Proposes
            dialogue.append(Turn(
                turn_id=turn_idx, role=Role.EXPERT.value, action_type=ActionType.PROPOSE.value,
                utterance=random.choice(self.expert_proposals).format(label=label_text),
                elements_involved=[], is_repair=False
            ))
            turn_idx += 1
            
            # Simulate 15% chance of Repair (CSCW artifact)
            if random.random() < 0.15 and len(chunk) > 0:
                modified_label = chunk[0].label + "处理"
                dialogue.append(Turn(
                    turn_id=turn_idx, role=Role.EXPERT.value, action_type=ActionType.REPAIR.value,
                    utterance=random.choice(self.expert_repairs).format(label=modified_label),
                    elements_involved=[], is_repair=True
                ))
                label_text = modified_label
                turn_idx += 1

            # 2. Editor Clarifies/Grounds
            shape_desc = self._get_shape_desc(chunk[0]) if chunk else "节点"
            dialogue.append(Turn(
                turn_id=turn_idx, role=Role.EDITOR.value, action_type=ActionType.CLARIFY.value,
                utterance=random.choice(self.editor_clarifications).format(shape=shape_desc, label=label_text),
                elements_involved=[], is_repair=False
            ))
            turn_idx += 1
            
            # 3. Expert Confirms
            confirms = ["对的，就这样。", "没问题。", "可以，继续吧。", "嗯，这样看起来很清晰。"]
            dialogue.append(Turn(
                turn_id=turn_idx, role=Role.EXPERT.value, action_type=ActionType.CONFIRM.value,
                utterance=random.choice(confirms),
                elements_involved=[], is_repair=False
            ))
            turn_idx += 1
            
            # 4. Editor Executes (Implicit in the data structure, this represents the code diff)
            dialogue.append(Turn(
                turn_id=turn_idx, role=Role.EDITOR.value, action_type=ActionType.EXECUTE.value,
                utterance="[系统日志: Editor 更新了图表代码以反映上述结构]",
                elements_involved=[e.id for e in chunk], is_repair=False
            ))
            turn_idx += 1
            
        return dialogue

# 为了兼容旧的 DiagramParser，我们在这里包含简化的解析器
class SimpleParser:
    def parse(self, code):
        # 非常基础的提取，为了展示结构，实际应用中会复用原版的 parser
        nodes = re.findall(r'(\w+)\s*[\[\(\{]\s*([^\]\)\}]+)\s*[\]\)\}]', code)
        return [DiagramElement(id=n[0], type='node', label=n[1], properties={}, dependencies=[]) for n in nodes]

def run_cscw_engine(input_code: str):
    parser = SimpleParser()
    elements = parser.parse(input_code)
    if not elements:
        # Fallback for complex diagrams
        elements = [DiagramElement(id="root", type="generic", label="主架构", properties={}, dependencies=[])]
        
    generator = CSCWDialogueGenerator()
    return generator.generate_grounded_dialogue(elements)
