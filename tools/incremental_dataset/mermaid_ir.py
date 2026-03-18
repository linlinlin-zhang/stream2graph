from __future__ import annotations

import re

from tools.eval.common import normalize_whitespace
from tools.eval.metrics import canonical_diagram_type, normalize_mermaid
from tools.incremental_dataset.schema import GraphEdge, GraphGroup, GraphIR, GraphNode, SourceSample


NODE_DECL_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]{0,63})\s*"
    r"(\[\[[^\]]+\]\]|\[[^\]]+\]|\(\([^)]*\)\)|\([^)]*\)|\{[^}]*\}|>[^]\n]*\])"
)
SIMPLE_NODE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]{0,63})\s*$")
SEQUENCE_ACTOR_RE = re.compile(
    r"^\s*(participant|actor|database|entity|queue|boundary|control|collections?)\s+([A-Za-z][A-Za-z0-9_]{0,63})"
    r"(?:\s+as\s+(.*))?$",
    flags=re.IGNORECASE,
)
EDGE_LINE_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]{0,63})(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|>[^]\n]*\])?\s*"
    r"(<<?[-.=ox]+>?|-->|==>|-.->|->>|-->>|<<--|<--|<->)\s*"
    r"(?:\|([^|]+)\|\s*)?"
    r"([A-Za-z][A-Za-z0-9_]{0,63})"
    r"(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|>[^]\n]*\])?"
    r"(?:\s*:\s*(.*))?$"
)
SUBGRAPH_RE = re.compile(r'^\s*subgraph\s+(.+?)\s*$', flags=re.IGNORECASE)
STYLE_RE = re.compile(r"^\s*(classDef|class|style|linkStyle)\b", flags=re.IGNORECASE)


def _strip_node_shape(raw: str) -> str:
    value = (raw or "").strip()
    wrappers = ("[[", "]]"), ("[", "]"), ("((", "))"), ("(", ")"), ("{", "}"), (">", "]")
    for lhs, rhs in wrappers:
        if value.startswith(lhs) and value.endswith(rhs):
            value = value[len(lhs) : len(value) - len(rhs)]
            break
    value = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    value = re.sub(r"<[^>]+>", "", value)
    value = value.strip("\"' ")
    return normalize_whitespace(value)


def _clean_group_label(raw: str, fallback: str) -> tuple[str, str]:
    value = (raw or "").strip()
    explicit_id = ""
    explicit_label = value
    id_match = re.match(r'^([A-Za-z][A-Za-z0-9_]{0,63})\s*(.*)$', value)
    if id_match and id_match.group(2).strip():
        explicit_id = id_match.group(1)
        explicit_label = id_match.group(2).strip()
    explicit_label = explicit_label.strip("\"' ")
    explicit_label = _strip_node_shape(explicit_label) or explicit_label
    explicit_label = normalize_whitespace(explicit_label) or fallback
    return explicit_id or fallback, explicit_label


def parse_mermaid_to_graph_ir(sample: SourceSample) -> GraphIR:
    normalized = normalize_mermaid(sample.code)
    diagram_type = canonical_diagram_type(sample.diagram_type)
    nodes_by_id: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    groups_by_id: dict[str, GraphGroup] = {}
    group_stack: list[str] = []

    def ensure_node(node_id: str, label: str | None, kind: str, source_index: int) -> GraphNode:
        existing = nodes_by_id.get(node_id)
        parent = group_stack[-1] if group_stack else None
        if existing is None:
            node = GraphNode(
                id=node_id,
                label=normalize_whitespace(label or node_id) or node_id,
                kind=kind,
                parent=parent,
                source_index=source_index,
                metadata={"diagram_type": diagram_type},
            )
            nodes_by_id[node_id] = node
            if parent and parent in groups_by_id and node_id not in groups_by_id[parent].member_ids:
                groups_by_id[parent].member_ids.append(node_id)
            return node
        if label and not existing.label:
            existing.label = normalize_whitespace(label)
        if parent and existing.parent is None:
            existing.parent = parent
            if parent in groups_by_id and node_id not in groups_by_id[parent].member_ids:
                groups_by_id[parent].member_ids.append(node_id)
        return existing

    for line_index, line in enumerate(normalized.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%%") or stripped == "---":
            continue
        if stripped.lower().startswith(("graph ", "flowchart ", "sequencediagram", "statediagram", "erdiagram", "mindmap")):
            continue
        if stripped.lower() == "end":
            if group_stack:
                group_stack.pop()
            continue
        if STYLE_RE.match(stripped):
            continue

        subgraph_match = SUBGRAPH_RE.match(stripped)
        if subgraph_match:
            fallback_id = f"group_{len(groups_by_id) + 1}"
            group_id, group_label = _clean_group_label(subgraph_match.group(1), fallback_id)
            parent = group_stack[-1] if group_stack else None
            groups_by_id[group_id] = GraphGroup(
                id=group_id,
                label=group_label,
                parent=parent,
                source_index=line_index,
            )
            group_stack.append(group_id)
            continue

        sequence_match = SEQUENCE_ACTOR_RE.match(stripped)
        if sequence_match:
            actor_kind = sequence_match.group(1).lower()
            actor_id = sequence_match.group(2)
            actor_label = normalize_whitespace(sequence_match.group(3) or actor_id)
            ensure_node(actor_id, actor_label, actor_kind, line_index)
            continue

        edge_match = EDGE_LINE_RE.match(stripped)
        if edge_match:
            source_id = edge_match.group(1)
            label_from_pipe = normalize_whitespace(edge_match.group(3) or "")
            target_id = edge_match.group(4)
            label_from_suffix = normalize_whitespace(edge_match.group(5) or "")
            edge_label = label_from_pipe or label_from_suffix
            ensure_node(source_id, source_id, "node", line_index)
            ensure_node(target_id, target_id, "node", line_index)
            edges.append(
                GraphEdge(
                    id=f"e{len(edges) + 1}",
                    source=source_id,
                    target=target_id,
                    label=edge_label,
                    source_index=line_index,
                    metadata={"connector": edge_match.group(2)},
                )
            )
            continue

        node_match = NODE_DECL_RE.match(stripped)
        if node_match:
            node_id = node_match.group(1)
            node_label = _strip_node_shape(node_match.group(2)) or node_id
            ensure_node(node_id, node_label, "node", line_index)
            continue

        simple_node_match = SIMPLE_NODE_RE.match(stripped)
        if simple_node_match:
            node_id = simple_node_match.group(1)
            ensure_node(node_id, node_id, "node", line_index)

    return GraphIR(
        graph_id=sample.sample_id,
        diagram_type=diagram_type,
        nodes=sorted(nodes_by_id.values(), key=lambda item: (item.source_index, item.id)),
        edges=sorted(edges, key=lambda item: (item.source_index, item.id)),
        groups=sorted(groups_by_id.values(), key=lambda item: (item.source_index, item.id)),
        metadata={
            "source_path": sample.source_path,
            "compilation_status": sample.compilation_status,
            "content_size": sample.content_size,
            "normalized_code": normalized,
        },
    )
