from __future__ import annotations

from collections import Counter, defaultdict

from tools.incremental_dataset.schema import GraphIR, SourceSample


def recommend_stage_count(complexity_score: float) -> int:
    if complexity_score <= 5:
        return 1
    if complexity_score <= 11:
        return 2
    if complexity_score <= 18:
        return 3
    if complexity_score <= 28:
        return 4
    return 5


def build_profile(sample: SourceSample, graph_ir: GraphIR) -> dict:
    out_degree: Counter[str] = Counter()
    in_degree: Counter[str] = Counter()
    label_count = sum(1 for node in graph_ir.nodes if node.label and node.label != node.id)
    label_count += sum(1 for edge in graph_ir.edges if edge.label)

    for edge in graph_ir.edges:
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1

    branch_nodes = sum(1 for node in graph_ir.nodes if out_degree.get(node.id, 0) > 1)
    merge_nodes = sum(1 for node in graph_ir.nodes if in_degree.get(node.id, 0) > 1)
    isolated_nodes = sum(
        1 for node in graph_ir.nodes if out_degree.get(node.id, 0) == 0 and in_degree.get(node.id, 0) == 0
    )
    line_count = len([line for line in graph_ir.metadata.get("normalized_code", "").splitlines() if line.strip()])
    complexity_score = round(
        len(graph_ir.nodes) * 1.0
        + len(graph_ir.edges) * 1.3
        + len(graph_ir.groups) * 2.1
        + branch_nodes * 1.8
        + merge_nodes * 1.2
        + label_count * 0.4
        + line_count * 0.08,
        4,
    )

    return {
        "sample_id": sample.sample_id,
        "split": sample.split,
        "diagram_type": sample.diagram_type,
        "node_count": len(graph_ir.nodes),
        "edge_count": len(graph_ir.edges),
        "group_count": len(graph_ir.groups),
        "label_count": label_count,
        "branch_nodes": branch_nodes,
        "merge_nodes": merge_nodes,
        "isolated_nodes": isolated_nodes,
        "line_count": line_count,
        "content_size": sample.content_size,
        "compile_success": sample.compilation_status.lower() == "success",
        "augmented": sample.sample_id.startswith("aug_"),
        "complexity_score": complexity_score,
        "recommended_stage_count": recommend_stage_count(complexity_score),
        "source": sample.source,
        "license": sample.license,
    }


def assign_complexity_buckets(profiles: list[dict], bucket_count: int = 5) -> None:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for profile in profiles:
        by_type[str(profile["diagram_type"])].append(profile)

    for diagram_type, rows in by_type.items():
        ordered = sorted(rows, key=lambda item: (float(item["complexity_score"]), item["sample_id"]))
        total = len(ordered)
        for index, row in enumerate(ordered):
            bucket = min(bucket_count, max(1, int(index * bucket_count / max(total, 1)) + 1))
            row["complexity_bucket"] = bucket
            row["complexity_bucket_label"] = f"{diagram_type}_c{bucket}"
