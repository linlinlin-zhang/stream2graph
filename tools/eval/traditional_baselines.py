from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from tools.eval.common import normalize_whitespace, repo_root
from tools.eval.dataset import EvaluationSample, sample_to_transcript_rows


SCRIPTS_DIR = repo_root() / "versions" / "v3_2026-02-27_latest_9k_cscw" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from asr_stream_adapter import ASRChunk  # noqa: E402
from run_realtime_pipeline import run_realtime_pipeline  # noqa: E402
from streaming_intent_engine import EngineConfig  # noqa: E402


DIAGRAM_TYPE_PROXY_INTENT = {
    "architecture": "structural",
    "block-beta": "structural",
    "c4context": "structural",
    "class": "structural",
    "er": "relational",
    "flowchart": "sequential",
    "gantt": "sequential",
    "gitgraph": "sequential",
    "graph": "sequential",
    "mindmap": "classification",
    "pie": "contrastive",
    "requirementdiagram": "structural",
    "sequence": "sequential",
    "sequencediagram": "sequential",
    "stateDiagram": "sequential",
    "stateDiagram-v2": "sequential",
    "statediagram": "sequential",
}


@dataclass
class TraditionalBaselineOutput:
    generated_code: str
    raw_output_text: str
    latency_ms: float
    pipeline: dict[str, Any]
    metadata: dict[str, Any]


def proxy_intent_for_diagram_type(diagram_type: str) -> str:
    return DIAGRAM_TYPE_PROXY_INTENT.get((diagram_type or "").strip(), "generic")


def _safe_id(raw: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", (raw or "").strip())
    value = value.strip("_")
    if not value:
        value = "n"
    if not value[0].isalpha():
        value = f"n_{value}"
    return value[:64]


def _safe_label(raw: str, fallback: str) -> str:
    label = normalize_whitespace(raw or "").replace('"', "'")
    return label[:80] if label else fallback


def _transcript_rows_with_proxy_intent(
    sample: EvaluationSample,
    *,
    interval_ms: int,
    expected_intent_strategy: str,
) -> list[dict]:
    rows = sample_to_transcript_rows(sample, interval_ms=interval_ms, expected_intent_map=None)
    if expected_intent_strategy != "diagram_type_proxy":
        return rows
    proxy = proxy_intent_for_diagram_type(sample.diagram_type)
    for row in rows:
        action_type = str(row.get("metadata", {}).get("action_type", ""))
        if action_type in {"propose", "clarify", "execute", "repair"}:
            row["expected_intent"] = proxy
        else:
            row["expected_intent"] = None
    return rows


def _collect_graph_state(pipeline: dict[str, Any], max_nodes: int = 24, max_edges: int = 48) -> tuple[list[dict], list[dict]]:
    renderer_state = pipeline.get("renderer_state", {})
    raw_nodes = renderer_state.get("nodes", [])
    raw_edges = renderer_state.get("edges", [])
    nodes = list(raw_nodes)[:max_nodes]
    allowed_ids = {str(node.get("id")) for node in nodes}
    edges = [
        edge
        for edge in raw_edges
        if str(edge.get("from")) in allowed_ids and str(edge.get("to")) in allowed_ids
    ][:max_edges]
    return nodes, edges


def _render_flowchart(nodes: list[dict], edges: list[dict], direction: str = "TD") -> str:
    lines = [f"flowchart {direction}"]
    id_map = {}
    for index, node in enumerate(nodes, start=1):
        safe_id = _safe_id(str(node.get("id") or f"n{index}"))
        label = _safe_label(str(node.get("label", "")), f"Node {index}")
        id_map[str(node.get("id"))] = safe_id
        lines.append(f'  {safe_id}["{label}"]')
    for edge in edges:
        src = id_map.get(str(edge.get("from")))
        dst = id_map.get(str(edge.get("to")))
        if src and dst:
            lines.append(f"  {src} --> {dst}")
    return "\n".join(lines) + "\n"


def _render_state_diagram(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["stateDiagram-v2"]
    id_map = {}
    for index, node in enumerate(nodes, start=1):
        safe_id = _safe_id(str(node.get("id") or f"s{index}"))
        label = _safe_label(str(node.get("label", "")), f"State {index}")
        id_map[str(node.get("id"))] = safe_id
        lines.append(f'  state "{label}" as {safe_id}')
    if nodes:
        first_id = id_map.get(str(nodes[0].get("id")))
        if first_id:
            lines.append(f"  [*] --> {first_id}")
    emitted_edge = False
    for edge in edges:
        src = id_map.get(str(edge.get("from")))
        dst = id_map.get(str(edge.get("to")))
        if src and dst:
            lines.append(f"  {src} --> {dst}")
            emitted_edge = True
    if not emitted_edge and len(nodes) >= 2:
        lines.append(f"  {id_map[str(nodes[0]['id'])]} --> {id_map[str(nodes[1]['id'])]}")
    return "\n".join(lines) + "\n"


def _render_sequence_diagram(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["sequenceDiagram"]
    id_map = {}
    for index, node in enumerate(nodes, start=1):
        safe_id = _safe_id(str(node.get("id") or f"p{index}"))
        label = _safe_label(str(node.get("label", "")), f"Actor {index}")
        id_map[str(node.get("id"))] = safe_id
        lines.append(f"  participant {safe_id} as {label}")
    emitted_edge = False
    for step, edge in enumerate(edges, start=1):
        src = id_map.get(str(edge.get("from")))
        dst = id_map.get(str(edge.get("to")))
        if src and dst:
            lines.append(f"  {src}->>{dst}: step {step}")
            emitted_edge = True
    if not emitted_edge and len(nodes) >= 2:
        src = id_map[str(nodes[0]["id"])]
        dst = id_map[str(nodes[1]["id"])]
        lines.append(f"  {src}->>{dst}: start")
    return "\n".join(lines) + "\n"


def _render_pie(nodes: list[dict]) -> str:
    lines = ["pie", "  title Heuristic Summary"]
    if not nodes:
        lines.append('  "Unknown" : 1')
        return "\n".join(lines) + "\n"
    for index, node in enumerate(nodes[:8], start=1):
        label = _safe_label(str(node.get("label", "")), f"Slice {index}")
        lines.append(f'  "{label}" : 1')
    return "\n".join(lines) + "\n"


def _render_gantt(nodes: list[dict]) -> str:
    lines = ["gantt", "  title Heuristic Schedule", "  dateFormat YYYY-MM-DD", "  section Tasks"]
    if not nodes:
        lines.append("  Task 1 :t1, 2026-01-01, 1d")
        return "\n".join(lines) + "\n"
    for index, node in enumerate(nodes[:8], start=1):
        label = _safe_label(str(node.get("label", "")), f"Task {index}")
        day = index if index < 28 else 28
        lines.append(f"  {label} :t{index}, 2026-01-{day:02d}, 1d")
    return "\n".join(lines) + "\n"


def _render_mindmap(nodes: list[dict]) -> str:
    root = _safe_label(str(nodes[0].get("label", "")), "Heuristic Root") if nodes else "Heuristic Root"
    lines = ["mindmap", f"  root(({root}))"]
    for index, node in enumerate(nodes[1:9], start=1):
        label = _safe_label(str(node.get("label", "")), f"Item {index}")
        lines.append(f"    {label}")
    return "\n".join(lines) + "\n"


def _render_class_diagram(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["classDiagram"]
    id_map = {}
    for index, node in enumerate(nodes, start=1):
        safe_id = _safe_id(str(node.get("id") or f"c{index}"))
        label = _safe_label(str(node.get("label", "")), f"Class {index}")
        id_map[str(node.get("id"))] = safe_id
        lines.append(f'  class {safe_id}["{label}"]')
    for edge in edges:
        src = id_map.get(str(edge.get("from")))
        dst = id_map.get(str(edge.get("to")))
        if src and dst:
            lines.append(f"  {src} --> {dst}")
    return "\n".join(lines) + "\n"


def _render_er_diagram(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["erDiagram"]
    id_map = {}
    for index, node in enumerate(nodes, start=1):
        safe_id = _safe_id(str(node.get("id") or f"e{index}")).upper()
        id_map[str(node.get("id"))] = safe_id
        lines.extend(
            [
                f"  {safe_id} {{",
                "    string label",
                "  }",
            ]
        )
    emitted = False
    for edge in edges:
        src = id_map.get(str(edge.get("from")))
        dst = id_map.get(str(edge.get("to")))
        if src and dst:
            lines.append(f"  {src} ||--o{{ {dst} : relates")
            emitted = True
    if not emitted and len(nodes) >= 2:
        lines.append(f"  {id_map[str(nodes[0]['id'])]} ||--o{{ {id_map[str(nodes[1]['id'])]} : relates")
    return "\n".join(lines) + "\n"


def _render_gitgraph(nodes: list[dict]) -> str:
    lines = ["gitGraph"]
    for index, node in enumerate(nodes[:8], start=1):
        label = _safe_label(str(node.get("label", "")), f"commit {index}")
        lines.append(f'  commit id: "{label}"')
    if len(lines) == 1:
        lines.append('  commit id: "initial"')
    return "\n".join(lines) + "\n"


def _render_requirementdiagram(nodes: list[dict]) -> str:
    lines = ["requirementDiagram"]
    if not nodes:
        lines.extend(
            [
                "  requirement req1 {",
                "    id: REQ-1",
                "    text: heuristic requirement",
                "    risk: medium",
                "    verifymethod: test",
                "  }",
            ]
        )
        return "\n".join(lines) + "\n"
    for index, node in enumerate(nodes[:6], start=1):
        safe_id = _safe_id(str(node.get("id") or f"req{index}"))
        label = _safe_label(str(node.get("label", "")), f"Requirement {index}")
        lines.extend(
            [
                f"  requirement {safe_id} {{",
                f"    id: REQ-{index}",
                f"    text: {label}",
                "    risk: medium",
                "    verifymethod: test",
                "  }",
            ]
        )
    return "\n".join(lines) + "\n"


def render_traditional_mermaid(sample: EvaluationSample, pipeline: dict[str, Any], export_style: str = "auto") -> tuple[str, str]:
    nodes, edges = _collect_graph_state(pipeline)
    normalized_type = (sample.diagram_type or "").strip().lower()

    if export_style == "flowchart":
        return _render_flowchart(nodes, edges, direction="TD"), "flowchart"
    if export_style == "state":
        return _render_state_diagram(nodes, edges), "stateDiagram-v2"

    if normalized_type in {"flowchart", "graph"}:
        return _render_flowchart(nodes, edges, direction="TD"), "flowchart"
    if normalized_type in {"architecture", "block-beta", "c4context", "packet-beta"}:
        return _render_flowchart(nodes, edges, direction="LR"), "flowchart"
    if normalized_type in {"statediagram", "stateDiagram".lower(), "statediagram-v2"}:
        return _render_state_diagram(nodes, edges), "stateDiagram-v2"
    if normalized_type in {"sequence", "sequencediagram"}:
        return _render_sequence_diagram(nodes, edges), "sequenceDiagram"
    if normalized_type == "pie":
        return _render_pie(nodes), "pie"
    if normalized_type == "gantt":
        return _render_gantt(nodes), "gantt"
    if normalized_type == "mindmap":
        return _render_mindmap(nodes), "mindmap"
    if normalized_type == "class":
        return _render_class_diagram(nodes, edges), "classDiagram"
    if normalized_type == "er":
        return _render_er_diagram(nodes, edges), "erDiagram"
    if normalized_type == "gitgraph":
        return _render_gitgraph(nodes), "gitGraph"
    if normalized_type == "requirementdiagram":
        return _render_requirementdiagram(nodes), "requirementDiagram"
    return _render_flowchart(nodes, edges, direction="TD"), "flowchart"


class TraditionalBaselineRunner:
    def __init__(
        self,
        *,
        turn_interval_ms: int = 450,
        realtime: bool = False,
        time_scale: float = 1.0,
        max_chunks: int = 0,
        min_wait_k: int = 1,
        base_wait_k: int = 2,
        max_wait_k: int = 4,
        expected_intent_strategy: str = "none",
        diagram_export_style: str = "auto",
    ) -> None:
        self.turn_interval_ms = turn_interval_ms
        self.realtime = realtime
        self.time_scale = time_scale
        self.max_chunks = max_chunks
        self.engine_config = EngineConfig(
            min_wait_k=min_wait_k,
            base_wait_k=base_wait_k,
            max_wait_k=max_wait_k,
        )
        self.expected_intent_strategy = expected_intent_strategy
        self.diagram_export_style = diagram_export_style

    def run_sample(self, sample: EvaluationSample) -> TraditionalBaselineOutput:
        t0 = time.time()
        transcript_rows = _transcript_rows_with_proxy_intent(
            sample,
            interval_ms=self.turn_interval_ms,
            expected_intent_strategy=self.expected_intent_strategy,
        )
        chunks = [
            ASRChunk(
                timestamp_ms=int(row["timestamp_ms"]),
                text=str(row["text"]),
                speaker=str(row.get("speaker", "user")),
                is_final=bool(row.get("is_final", True)),
                expected_intent=row.get("expected_intent"),
                metadata=row.get("metadata", {}),
            )
            for row in transcript_rows
        ]
        pipeline = run_realtime_pipeline(
            chunks=chunks,
            realtime=self.realtime,
            time_scale=self.time_scale,
            max_chunks=self.max_chunks,
            config=self.engine_config,
        )
        generated_code, render_strategy = render_traditional_mermaid(
            sample,
            pipeline,
            export_style=self.diagram_export_style,
        )
        latency_ms = (time.time() - t0) * 1000.0
        metadata = {
            "traditional_baseline": {
                "render_strategy": render_strategy,
                "expected_intent_strategy": self.expected_intent_strategy,
                "pipeline_summary": pipeline.get("summary", {}),
                "engine_report": pipeline.get("engine_report", {}),
            }
        }
        return TraditionalBaselineOutput(
            generated_code=generated_code,
            raw_output_text=generated_code,
            latency_ms=round(latency_ms, 4),
            pipeline=pipeline,
            metadata=metadata,
        )
