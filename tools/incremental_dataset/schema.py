from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceSample:
    sample_id: str
    split: str
    diagram_type: str
    code: str
    source_path: str
    source: str = ""
    license: str = ""
    compilation_status: str = ""
    content_size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "split": self.split,
            "diagram_type": self.diagram_type,
            "code": self.code,
            "source_path": self.source_path,
            "source": self.source,
            "license": self.license,
            "compilation_status": self.compilation_status,
            "content_size": self.content_size,
            "metadata": self.metadata,
        }


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str = "node"
    parent: str | None = None
    source_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "parent": self.parent,
            "source_index": self.source_index,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    label: str = ""
    kind: str = "edge"
    source_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "kind": self.kind,
            "source_index": self.source_index,
            "metadata": self.metadata,
        }


@dataclass
class GraphGroup:
    id: str
    label: str
    parent: str | None = None
    member_ids: list[str] = field(default_factory=list)
    source_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "parent": self.parent,
            "member_ids": self.member_ids,
            "source_index": self.source_index,
            "metadata": self.metadata,
        }


@dataclass
class GraphIR:
    graph_id: str
    diagram_type: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    groups: list[GraphGroup] = field(default_factory=list)
    styles: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "diagram_type": self.diagram_type,
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
            "groups": [group.to_payload() for group in self.groups],
            "styles": self.styles,
            "metadata": self.metadata,
        }


@dataclass
class StageState:
    stage_index: int
    stage_name: str
    stage_description: str
    graph_ir: GraphIR
    delta_ops: list[dict[str, Any]] = field(default_factory=list)
    preview_mermaid: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "stage_description": self.stage_description,
            "graph_ir": self.graph_ir.to_payload(),
            "delta_ops": self.delta_ops,
            "preview_mermaid": self.preview_mermaid,
            "metrics": self.metrics,
        }
