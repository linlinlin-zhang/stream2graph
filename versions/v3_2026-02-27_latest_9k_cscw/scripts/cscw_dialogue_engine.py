#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSCW-Grade Dialogue Reverse Engineering Engine (V2)

升级目标:
1. 从"简单正则 + 固定模板"升级到"图结构解析 + 动态分段 + 意图驱动对话生成"
2. 引入 Wait-k 式增量生成策略，避免一次性大段输出
3. 输出可用于后续分析的结构化元数据
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from statistics import median
from typing import Dict, List, Optional, Set, Tuple


class Role(Enum):
    EXPERT = "Domain_Expert"
    EDITOR = "Diagram_Editor"


class ActionType(Enum):
    PROPOSE = "propose"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    REPAIR = "repair"
    EXECUTE = "execute"


class IntentType(Enum):
    SEQUENTIAL = "sequential"
    STRUCTURAL = "structural"
    CLASSIFICATION = "classification"
    RELATIONAL = "relational"
    CONTRASTIVE = "contrastive"
    GENERIC = "generic"


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


@dataclass
class ParsedDiagram:
    diagram_type: str
    elements: List[DiagramElement]
    edge_count: int
    parse_confidence: float
    parser_warnings: List[str]


class MermaidParser:
    EDGE_PATTERNS = [
        r"([A-Za-z0-9_]+)\s*--?>+\s*([A-Za-z0-9_]+)",
        r"([A-Za-z0-9_]+)\s*-\.-+\s*([A-Za-z0-9_]+)",
        r"([A-Za-z0-9_]+)\s*==>+\s*([A-Za-z0-9_]+)",
        r"([A-Za-z0-9_]+)\s*:::\w+\s*--?>+\s*([A-Za-z0-9_]+)",
    ]
    NODE_PATTERN = re.compile(
        r"([A-Za-z0-9_]+)\s*[\[\(\{]\s*([^\]\)\}\n]{1,120})\s*[\]\)\}]"
    )

    def parse(self, code: str) -> ParsedDiagram:
        clean = self._normalize_code(code)
        diagram_type = self._detect_diagram_type(clean)

        if diagram_type == "sequence":
            return self._parse_sequence(clean, diagram_type)
        if diagram_type == "class":
            return self._parse_class(clean, diagram_type)
        if diagram_type == "er":
            return self._parse_er(clean, diagram_type)
        if diagram_type in {"stateDiagram", "state"}:
            return self._parse_state(clean, diagram_type)

        # 默认走 flowchart/graph/其他通用解析
        return self._parse_generic_graph(clean, diagram_type)

    def _normalize_code(self, code: str) -> str:
        if not isinstance(code, str):
            return ""
        c = code.strip().replace("\r\n", "\n")
        c = re.sub(r"^```(?:mermaid)?\s*", "", c, flags=re.IGNORECASE)
        c = re.sub(r"```$", "", c.strip())
        return c

    def _detect_diagram_type(self, code: str) -> str:
        for line in code.splitlines():
            ln = line.strip().lower()
            if not ln or ln.startswith("%%"):
                continue
            if ln.startswith("flowchart") or ln.startswith("graph "):
                return "flowchart"
            if ln.startswith("sequencediagram"):
                return "sequence"
            if ln.startswith("classdiagram"):
                return "class"
            if ln.startswith("erdiagram"):
                return "er"
            if ln.startswith("statediagram"):
                return "stateDiagram"
            if ln.startswith("mindmap"):
                return "mindmap"
            if ln.startswith("gantt"):
                return "gantt"
            if ln.startswith("timeline"):
                return "timeline"
            if ln.startswith("journey"):
                return "journey"
            if ln.startswith("gitgraph"):
                return "gitGraph"
            if ln.startswith("architecture"):
                return "architecture"
            if ln.startswith("kanban"):
                return "kanban"
            if ln.startswith("pie"):
                return "pie"
            if ln.startswith("xychart"):
                return "xychart"
            if ln.startswith("requirementdiagram"):
                return "requirementDiagram"
        return "generic"

    def _parse_generic_graph(self, code: str, diagram_type: str) -> ParsedDiagram:
        nodes: Dict[str, DiagramElement] = {}
        edges: List[Tuple[str, str]] = []
        warnings: List[str] = []

        # 1) 节点定义
        for m in self.NODE_PATTERN.finditer(code):
            node_id = m.group(1)
            raw_label = m.group(2)
            label = self._clean_label(raw_label) or node_id
            node_type = self._infer_node_type(raw_label)
            if node_id not in nodes:
                nodes[node_id] = DiagramElement(
                    id=node_id,
                    type=node_type,
                    label=label,
                    properties={"shape": node_type},
                    dependencies=[],
                )

        # 2) 边定义
        for p in self.EDGE_PATTERNS:
            for m in re.finditer(p, code):
                src = m.group(1)
                dst = m.group(2)
                edges.append((src, dst))
                if src not in nodes:
                    nodes[src] = DiagramElement(
                        id=src,
                        type="rect",
                        label=src,
                        properties={"shape": "rect"},
                        dependencies=[],
                    )
                if dst not in nodes:
                    nodes[dst] = DiagramElement(
                        id=dst,
                        type="rect",
                        label=dst,
                        properties={"shape": "rect"},
                        dependencies=[],
                    )

        for src, dst in edges:
            if src != dst and src not in nodes[dst].dependencies:
                nodes[dst].dependencies.append(src)

        # 3) 兜底：如果节点仍为空，尝试抽取标题词
        if not nodes:
            fallback_labels = self._fallback_labels(code)
            if not fallback_labels:
                fallback_labels = ["主流程"]
            for i, lb in enumerate(fallback_labels, start=1):
                nid = f"x{i}"
                nodes[nid] = DiagramElement(
                    id=nid,
                    type="rect",
                    label=lb,
                    properties={"shape": "rect"},
                    dependencies=[f"x{i-1}"] if i > 1 else [],
                )
            edges = [(f"x{i}", f"x{i+1}") for i in range(1, len(fallback_labels))]
            warnings.append("fallback_label_extraction_used")

        placeholder_labels = sum(1 for e in nodes.values() if e.label == e.id)
        if nodes and placeholder_labels / len(nodes) > 0.35:
            warnings.append("high_placeholder_label_ratio")

        confidence = self._estimate_confidence(
            node_count=len(nodes),
            edge_count=len(edges),
            warnings=warnings,
            code=code,
        )
        return ParsedDiagram(
            diagram_type=diagram_type,
            elements=list(nodes.values()),
            edge_count=len(edges),
            parse_confidence=confidence,
            parser_warnings=warnings,
        )

    def _parse_sequence(self, code: str, diagram_type: str) -> ParsedDiagram:
        nodes: Dict[str, DiagramElement] = {}
        warnings: List[str] = []
        participants = re.findall(r"participant\s+([A-Za-z0-9_]+)", code, flags=re.IGNORECASE)
        messages = re.findall(r"([A-Za-z0-9_]+)\s*[-=]+>+\s*([A-Za-z0-9_]+)\s*:\s*([^\n]+)", code)

        for p in participants:
            if p not in nodes:
                nodes[p] = DiagramElement(
                    id=p,
                    type="actor",
                    label=self._clean_label(p),
                    properties={"shape": "actor"},
                    dependencies=[],
                )

        turn_idx = 1
        for src, dst, msg in messages:
            eid = f"m{turn_idx}"
            lb = self._clean_label(msg) or f"{src}->{dst}"
            nodes[eid] = DiagramElement(
                id=eid,
                type="message",
                label=lb,
                properties={"shape": "rect", "src": src, "dst": dst},
                dependencies=[src, dst],
            )
            turn_idx += 1

        if not nodes:
            warnings.append("sequence_fallback_used")
            nodes["x1"] = DiagramElement(
                id="x1",
                type="actor",
                label="参与者",
                properties={"shape": "actor"},
                dependencies=[],
            )

        confidence = self._estimate_confidence(len(nodes), max(0, len(messages)), warnings, code)
        return ParsedDiagram(
            diagram_type=diagram_type,
            elements=list(nodes.values()),
            edge_count=len(messages),
            parse_confidence=confidence,
            parser_warnings=warnings,
        )

    def _parse_class(self, code: str, diagram_type: str) -> ParsedDiagram:
        nodes: Dict[str, DiagramElement] = {}
        warnings: List[str] = []
        class_defs = re.findall(r"\bclass\s+([A-Za-z0-9_]+)", code)
        relations = re.findall(r"([A-Za-z0-9_]+)\s*[<|o*.-]+>\s*([A-Za-z0-9_]+)", code)

        for cls in class_defs:
            nodes[cls] = DiagramElement(
                id=cls,
                type="class",
                label=self._clean_label(cls),
                properties={"shape": "class"},
                dependencies=[],
            )

        for src, dst in relations:
            if src not in nodes:
                nodes[src] = DiagramElement(src, "class", src, {"shape": "class"}, [])
            if dst not in nodes:
                nodes[dst] = DiagramElement(dst, "class", dst, {"shape": "class"}, [])
            if src not in nodes[dst].dependencies:
                nodes[dst].dependencies.append(src)

        if not nodes:
            warnings.append("class_fallback_used")
            return self._parse_generic_graph(code, "class")

        confidence = self._estimate_confidence(len(nodes), len(relations), warnings, code)
        return ParsedDiagram(
            diagram_type=diagram_type,
            elements=list(nodes.values()),
            edge_count=len(relations),
            parse_confidence=confidence,
            parser_warnings=warnings,
        )

    def _parse_er(self, code: str, diagram_type: str) -> ParsedDiagram:
        nodes: Dict[str, DiagramElement] = {}
        warnings: List[str] = []
        entities = re.findall(r"^\s*([A-Za-z0-9_]+)\s*\{", code, flags=re.MULTILINE)
        relations = re.findall(
            r"([A-Za-z0-9_]+)\s*\|\|--o\{\s*([A-Za-z0-9_]+)|([A-Za-z0-9_]+)\s*}\|--\|\{\s*([A-Za-z0-9_]+)",
            code,
        )

        for ent in entities:
            nodes[ent] = DiagramElement(
                id=ent,
                type="entity",
                label=self._clean_label(ent),
                properties={"shape": "database"},
                dependencies=[],
            )

        edge_count = 0
        for r in relations:
            src = r[0] or r[2]
            dst = r[1] or r[3]
            if not src or not dst:
                continue
            edge_count += 1
            if src not in nodes:
                nodes[src] = DiagramElement(src, "entity", src, {"shape": "database"}, [])
            if dst not in nodes:
                nodes[dst] = DiagramElement(dst, "entity", dst, {"shape": "database"}, [])
            if src not in nodes[dst].dependencies:
                nodes[dst].dependencies.append(src)

        if not nodes:
            warnings.append("er_fallback_used")
            return self._parse_generic_graph(code, "er")

        confidence = self._estimate_confidence(len(nodes), edge_count, warnings, code)
        return ParsedDiagram(
            diagram_type=diagram_type,
            elements=list(nodes.values()),
            edge_count=edge_count,
            parse_confidence=confidence,
            parser_warnings=warnings,
        )

    def _parse_state(self, code: str, diagram_type: str) -> ParsedDiagram:
        nodes: Dict[str, DiagramElement] = {}
        warnings: List[str] = []
        transitions = re.findall(r"([A-Za-z0-9_\[\]]+)\s*-->\s*([A-Za-z0-9_\[\]]+)", code)

        for src, dst in transitions:
            src_n = self._clean_label(src.replace("[", "").replace("]", "")) or src
            dst_n = self._clean_label(dst.replace("[", "").replace("]", "")) or dst
            if src_n not in nodes:
                nodes[src_n] = DiagramElement(src_n, "state", src_n, {"shape": "rect"}, [])
            if dst_n not in nodes:
                nodes[dst_n] = DiagramElement(dst_n, "state", dst_n, {"shape": "rect"}, [])
            if src_n not in nodes[dst_n].dependencies:
                nodes[dst_n].dependencies.append(src_n)

        if not nodes:
            warnings.append("state_fallback_used")
            return self._parse_generic_graph(code, "stateDiagram")

        confidence = self._estimate_confidence(len(nodes), len(transitions), warnings, code)
        return ParsedDiagram(
            diagram_type=diagram_type,
            elements=list(nodes.values()),
            edge_count=len(transitions),
            parse_confidence=confidence,
            parser_warnings=warnings,
        )

    def _fallback_labels(self, code: str) -> List[str]:
        quoted = re.findall(r'"([^"\n]{2,80})"', code)
        if quoted:
            return [self._clean_label(x) for x in quoted[:8] if self._clean_label(x)]

        bracketed = re.findall(r"\[([^\]\n]{2,80})\]", code)
        if bracketed:
            return [self._clean_label(x) for x in bracketed[:8] if self._clean_label(x)]

        words = [w for w in re.split(r"[\s,;:(){}<>]+", code) if len(w) >= 3]
        uniq = []
        seen: Set[str] = set()
        for w in words:
            w2 = self._clean_label(w)
            if not w2:
                continue
            lw = w2.lower()
            if lw not in seen:
                seen.add(lw)
                uniq.append(w2)
            if len(uniq) >= 8:
                break
        return uniq

    def _clean_label(self, text: str) -> str:
        t = str(text or "")
        t = t.replace("<br/>", " ").replace("<br>", " ")
        t = re.sub(r"\s+", " ", t).strip()
        t = re.sub(r"^[`'\"“”]+|[`'\"“”]+$", "", t).strip()
        # 过滤明显噪声字符
        t = re.sub(r"[^\w\u4e00-\u9fff\-\s:/.&+]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if t in {".", "-", "_", "/", ":"}:
            return ""
        if len(t) < 2:
            return ""
        # 过滤几乎全数字的标签
        if len(t) >= 4:
            digit_ratio = sum(1 for ch in t if ch.isdigit()) / max(len(t), 1)
            if digit_ratio > 0.75:
                return ""
        if len(t) > 48:
            t = t[:45] + "..."
        return t

    def _infer_node_type(self, raw_label: str) -> str:
        lb = raw_label.strip()
        if lb.startswith("{") or lb.endswith("}"):
            return "diamond"
        if lb.startswith("((") or lb.endswith("))"):
            return "circle"
        if "db" in lb.lower() or "database" in lb.lower():
            return "database"
        return "rect"

    def _estimate_confidence(
        self,
        node_count: int,
        edge_count: int,
        warnings: List[str],
        code: str,
    ) -> float:
        score = 0.4
        score += min(node_count / 15.0, 0.35)
        score += min(edge_count / 20.0, 0.25)
        if "graph" in code.lower() or "flowchart" in code.lower() or "diagram" in code.lower():
            score += 0.05
        score -= 0.08 * len(warnings)
        return max(0.2, min(score, 0.99))


class WindowPlanner:
    def __init__(self, min_chunk: int = 1, max_chunk: int = 4):
        self.min_chunk = min_chunk
        self.max_chunk = max_chunk

    def plan(self, parsed: ParsedDiagram) -> Tuple[List[List[DiagramElement]], int]:
        elems = parsed.elements
        if not elems:
            return [], 1

        levels = self._dependency_levels(elems)
        # 动态 chunk 依据图类型 + 元素规模
        base = 2
        if parsed.diagram_type in {"architecture", "class", "er"}:
            base = 3
        if len(elems) > 40:
            base = 4
        if parsed.diagram_type in {"sequence", "timeline"}:
            base = 2
        chunk_size = max(self.min_chunk, min(base, self.max_chunk))

        windows: List[List[DiagramElement]] = []
        for _, level_elements in sorted(levels.items()):
            level_sorted = sorted(level_elements, key=lambda x: (len(x.dependencies), x.id))
            if not level_sorted:
                continue
            # 在同层按 chunk 切片，模拟动态滑窗
            for i in range(0, len(level_sorted), chunk_size):
                windows.append(level_sorted[i : i + chunk_size])

        if not windows:
            windows = [elems[i : i + chunk_size] for i in range(0, len(elems), chunk_size)]

        # Wait-k: 每次至少观察 k 个新元素再触发一次 execute
        wait_k = 2 if parsed.parse_confidence >= 0.6 else 1
        return windows, wait_k

    def _dependency_levels(self, elements: List[DiagramElement]) -> Dict[int, List[DiagramElement]]:
        by_id = {e.id: e for e in elements}
        indeg = {e.id: 0 for e in elements}
        outgoing: Dict[str, List[str]] = defaultdict(list)
        for e in elements:
            for dep in e.dependencies:
                if dep in indeg:
                    indeg[e.id] += 1
                    outgoing[dep].append(e.id)

        q = deque([nid for nid, d in indeg.items() if d == 0])
        level_map: Dict[str, int] = {nid: 0 for nid in q}

        while q:
            cur = q.popleft()
            cur_level = level_map.get(cur, 0)
            for nxt in outgoing.get(cur, []):
                indeg[nxt] -= 1
                cand = cur_level + 1
                if cand > level_map.get(nxt, 0):
                    level_map[nxt] = cand
                if indeg[nxt] == 0:
                    q.append(nxt)

        # 有环或孤点
        for nid in by_id:
            level_map.setdefault(nid, 0)

        levels: Dict[int, List[DiagramElement]] = defaultdict(list)
        for nid, lv in level_map.items():
            levels[lv].append(by_id[nid])
        return levels


class CSCWDialogueGenerator:
    def __init__(self):
        self.intent_templates = {
            IntentType.SEQUENTIAL: {
                "propose": [
                    "先把 {label} 这一步明确下来，顺序上它比较关键。",
                    "下一步我建议处理 {label}，然后再往后推进。",
                    "这里可以把 {label} 放进主流程，便于后续串联。",
                ],
                "clarify": [
                    "我先按流程节点来画，把它标成 '{label}'，这样顺序对吗？",
                    "我会把 '{label}' 接在当前步骤后面，路径上保留可回溯关系。",
                ],
            },
            IntentType.STRUCTURAL: {
                "propose": [
                    "{label} 更像一个结构模块，我们需要单独表达它的职责边界。",
                    "这里建议把 {label} 作为核心组件，和上下游建立清晰连接。",
                ],
                "clarify": [
                    "我先把 '{label}' 画成结构节点，并标注与上层模块的依赖。",
                    "收到，我会把 '{label}' 放在架构层级里，保持模块关系稳定。",
                ],
            },
            IntentType.CLASSIFICATION: {
                "propose": [
                    "{label} 这一块适合归类展示，便于理解层次关系。",
                    "我建议把 {label} 放进分类分支，和同类项并列。",
                ],
                "clarify": [
                    "我把 '{label}' 放到对应分类节点下，层级这样安排可以吗？",
                    "这里我先按分类树组织 '{label}'，并保持同级对齐。",
                ],
            },
            IntentType.RELATIONAL: {
                "propose": [
                    "{label} 代表关键实体关系，最好把关联方向表达完整。",
                    "这一段重点是 {label} 的实体联系，先把主外键语义说清楚。",
                ],
                "clarify": [
                    "我会把 '{label}' 作为实体关系节点，先连上主要依赖。",
                    "收到，我按关系图语义处理 '{label}'，优先保证连接正确。",
                ],
            },
            IntentType.CONTRASTIVE: {
                "propose": [
                    "{label} 适合做对比展示，便于快速看出差异。",
                    "这里把 {label} 纳入对比维度，后续判断会更直观。",
                ],
                "clarify": [
                    "我先把 '{label}' 作为对比项放入图中，维度保持一致。",
                    "我会把 '{label}' 画进对比视图，确保读者能直接横向比较。",
                ],
            },
            IntentType.GENERIC: {
                "propose": [
                    "先把 {label} 这个关键点纳入图里，后面再细化。",
                    "这里建议先落实 {label}，作为后续讨论的锚点。",
                ],
                "clarify": [
                    "我先把 '{label}' 画出来，你确认下表意是否准确？",
                    "收到，我按当前语义把 '{label}' 加到图结构里。",
                ],
            },
        }
        self.confirm_pool = [
            "对，这样更清楚。",
            "可以，继续按这个结构推进。",
            "没问题，这个表达和我的意图一致。",
            "是的，先这么定。",
        ]
        self.repair_pool = [
            "我修正一下，刚才的叫法不够准确，改成 {label}。",
            "等下，名称需要微调，建议用 {label}。",
            "补充一下，应该强调 {label} 这个点。",
        ]

    def generate(self, code: str, min_turns: int = 4, max_turns: int = 120) -> Tuple[List[Turn], Dict]:
        parser = MermaidParser()
        parsed = parser.parse(code)
        planner = WindowPlanner()
        windows, wait_k = planner.plan(parsed)
        intent = self._infer_intent(parsed.diagram_type)

        seed = self._seed_from_text(code)
        rng = random.Random(seed)
        turns: List[Turn] = []
        turn_id = 1
        seen_utterances: Set[str] = set()
        repaired_count = 0
        intent_counter: Counter = Counter()

        pending: List[DiagramElement] = []
        for w in windows:
            pending.extend(w)
            intent_counter[intent.value] += 1
            labels = [e.label for e in w if e.label]
            main_label = self._compose_label(labels)
            shape = w[0].type if w else "rect"

            # PROPOSE
            turns.append(
                Turn(
                    turn_id=turn_id,
                    role=Role.EXPERT.value,
                    action_type=ActionType.PROPOSE.value,
                    utterance=self._pick(
                        self.intent_templates[intent]["propose"], rng, seen_utterances
                    ).format(label=main_label),
                    elements_involved=[],
                    is_repair=False,
                )
            )
            turn_id += 1

            # 可疑标签触发修复回合
            if self._needs_repair(main_label, parsed.parse_confidence, rng):
                repaired_count += 1
                turns.append(
                    Turn(
                        turn_id=turn_id,
                        role=Role.EXPERT.value,
                        action_type=ActionType.REPAIR.value,
                        utterance=self._pick(self.repair_pool, rng, seen_utterances).format(
                            label=main_label
                        ),
                        elements_involved=[],
                        is_repair=True,
                    )
                )
                turn_id += 1

            # CLARIFY
            clarify = self._pick(
                self.intent_templates[intent]["clarify"], rng, seen_utterances
            ).format(label=main_label, shape=shape)
            turns.append(
                Turn(
                    turn_id=turn_id,
                    role=Role.EDITOR.value,
                    action_type=ActionType.CLARIFY.value,
                    utterance=clarify,
                    elements_involved=[],
                    is_repair=False,
                )
            )
            turn_id += 1

            # CONFIRM
            turns.append(
                Turn(
                    turn_id=turn_id,
                    role=Role.EXPERT.value,
                    action_type=ActionType.CONFIRM.value,
                    utterance=self._pick(self.confirm_pool, rng, seen_utterances),
                    elements_involved=[],
                    is_repair=False,
                )
            )
            turn_id += 1

            # WAIT-K 后触发 EXECUTE
            if len(pending) >= wait_k:
                exec_elems = [e.id for e in pending]
                exec_msg = (
                    f"[系统日志: Editor 已按 Wait-{wait_k} 策略提交增量图更新，"
                    f"本次涉及 {len(exec_elems)} 个元素]"
                )
                turns.append(
                    Turn(
                        turn_id=turn_id,
                        role=Role.EDITOR.value,
                        action_type=ActionType.EXECUTE.value,
                        utterance=exec_msg,
                        elements_involved=exec_elems,
                        is_repair=False,
                    )
                )
                turn_id += 1
                pending = []

        if pending:
            turns.append(
                Turn(
                    turn_id=turn_id,
                    role=Role.EDITOR.value,
                    action_type=ActionType.EXECUTE.value,
                    utterance=f"[系统日志: Editor 完成收尾增量提交，涉及 {len(pending)} 个元素]",
                    elements_involved=[e.id for e in pending],
                    is_repair=False,
                )
            )
            turn_id += 1

        # 轮次修正
        turns = self._normalize_turns(turns, min_turns=min_turns, max_turns=max_turns)

        metadata = {
            "total_turns": len(turns),
            "repair_count": repaired_count,
            "grounding_acts_count": len(
                [t for t in turns if t.action_type in {"clarify", "confirm"}]
            ),
            "theoretical_framework": "Grounding in Communication (Clark & Brennan, 1991)",
            "algorithm_version": "cscw_dialogue_engine_v2",
            "diagram_type_detected": parsed.diagram_type,
            "intent_type": intent.value,
            "window_count": len(windows),
            "wait_k_used": wait_k,
            "node_count": len(parsed.elements),
            "edge_count": parsed.edge_count,
            "parse_confidence": round(parsed.parse_confidence, 4),
            "parser_warnings": parsed.parser_warnings,
            "intent_window_distribution": dict(intent_counter),
            "label_median_length": median([len(e.label) for e in parsed.elements]) if parsed.elements else 0,
        }
        return turns, metadata

    def _infer_intent(self, diagram_type: str) -> IntentType:
        t = (diagram_type or "").lower()
        if t in {"flowchart", "sequence", "statediagram", "state", "gantt", "timeline", "journey", "gitgraph"}:
            return IntentType.SEQUENTIAL
        if t in {"architecture", "class", "block-beta", "packet-beta", "c4context"}:
            return IntentType.STRUCTURAL
        if t in {"mindmap", "kanban", "requirementdiagram", "tree"}:
            return IntentType.CLASSIFICATION
        if t in {"er"}:
            return IntentType.RELATIONAL
        if t in {"pie", "xychart", "quadrantchart"}:
            return IntentType.CONTRASTIVE
        return IntentType.GENERIC

    def _seed_from_text(self, text: str) -> int:
        h = hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()
        return int(h[:12], 16)

    def _compose_label(self, labels: List[str]) -> str:
        uniq = []
        seen = set()
        for lb in labels:
            lb2 = (lb or "").strip()
            if not lb2:
                continue
            key = lb2.lower()
            if key not in seen:
                seen.add(key)
                uniq.append(lb2)
            if len(uniq) >= 3:
                break
        if not uniq:
            return "核心结构"
        if len(uniq) == 1:
            return uniq[0]
        return " / ".join(uniq)

    def _pick(self, pool: List[str], rng: random.Random, seen: Set[str]) -> str:
        if not pool:
            return ""
        candidates = pool[:]
        rng.shuffle(candidates)
        for c in candidates:
            if c not in seen:
                seen.add(c)
                return c
        # 允许重复但尽量随机
        return rng.choice(pool)

    def _needs_repair(self, label: str, conf: float, rng: random.Random) -> bool:
        noisy = bool(re.search(r"\bnull\b|^\d+$|[:/]{2,}|[A-Za-z0-9_]{20,}", label, flags=re.IGNORECASE))
        p = 0.08
        if conf < 0.55:
            p += 0.08
        if noisy:
            p += 0.12
        return rng.random() < min(p, 0.35)

    def _normalize_turns(self, turns: List[Turn], min_turns: int, max_turns: int) -> List[Turn]:
        if len(turns) > max_turns:
            turns = turns[:max_turns]

        while len(turns) < min_turns:
            next_id = len(turns) + 1
            if next_id % 2 == 1:
                turns.append(
                    Turn(
                        turn_id=next_id,
                        role=Role.EXPERT.value,
                        action_type=ActionType.CONFIRM.value,
                        utterance="可以，保持当前结构继续。",
                        elements_involved=[],
                        is_repair=False,
                    )
                )
            else:
                turns.append(
                    Turn(
                        turn_id=next_id,
                        role=Role.EDITOR.value,
                        action_type=ActionType.EXECUTE.value,
                        utterance="[系统日志: 为满足最小轮次，补充一次结构确认提交]",
                        elements_involved=[],
                        is_repair=False,
                    )
                )

        for i, t in enumerate(turns, start=1):
            t.turn_id = i
        return turns


def run_cscw_engine(input_code: str) -> List[Turn]:
    """兼容旧接口: 仅返回对话轮次。"""
    generator = CSCWDialogueGenerator()
    turns, _ = generator.generate(input_code)
    return turns


def run_cscw_engine_with_metadata(input_code: str) -> Tuple[List[Turn], Dict]:
    """新接口: 返回对话 + 元数据。"""
    generator = CSCWDialogueGenerator()
    return generator.generate(input_code)
