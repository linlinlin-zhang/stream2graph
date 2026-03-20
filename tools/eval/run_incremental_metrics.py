#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import read_json, read_jsonl, resolve_path, utc_iso, write_json
from tools.eval.reporting import aggregate_rows, group_rows, markdown_table, top_failure_examples, write_csv
from tools.incremental_dataset.schema import GraphEdge, GraphGroup, GraphIR, GraphNode
from tools.eval.incremental_dataset import DEFAULT_INCREMENTAL_RUN_ROOT
from tools.incremental_system.loader import _graph_ir_from_payload, load_runtime_sample


INCREMENTAL_METRIC_FIELDS = [
    "completed_all_stages",
    "final_matches_reference",
    "canonicalized_match",
    "exact_update_count_match",
    "stage_coverage_rate",
    "node_semantic_f1",
    "group_semantic_f1",
    "edge_semantic_f1",
    "attachment_semantic_f1",
    "entity_semantic_f1",
    "updates_emitted",
    "total_stages",
    "planner_calls",
    "gate_latency_mean_ms",
    "planner_latency_mean_ms",
    "total_model_latency_ms",
]

STRUCTURAL_STOPWORDS = {
    "node",
    "group",
    "edge",
    "participant",
    "actor",
    "cluster",
    "subgraph",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate incremental-system evaluation metrics.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--input-jsonl", type=str, default="")
    parser.add_argument("--output-dir", type=str, default="reports/evaluation/incremental/default_metrics")
    parser.add_argument("--run-root", type=str, default=DEFAULT_INCREMENTAL_RUN_ROOT)

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    args = parser.parse_args()
    if not args.input_jsonl:
        raise SystemExit("--input-jsonl is required.")
    return args


def _summary_markdown(summary: dict) -> str:
    overall_rows = []
    for field in INCREMENTAL_METRIC_FIELDS:
        metric = summary["overall"].get(field)
        if metric is None:
            continue
        overall_rows.append(
            {
                "metric": field,
                "count": metric.get("count"),
                "mean_or_rate": metric.get("mean", metric.get("rate")),
                "p50": metric.get("p50", ""),
                "p95": metric.get("p95", ""),
            }
        )

    by_type_rows = []
    for item in summary["slices"]["by_diagram_type"]:
        by_type_rows.append(
            {
                "diagram_type": item["group"],
                "count": item["count"],
                "final_match_rate": (item["metrics"].get("final_matches_reference") or {}).get("rate"),
                "canonicalized_match_rate": (item["metrics"].get("canonicalized_match") or {}).get("rate"),
                "entity_semantic_f1_mean": (item["metrics"].get("entity_semantic_f1") or {}).get("mean"),
                "coverage_mean": (item["metrics"].get("stage_coverage_rate") or {}).get("mean"),
                "planner_latency_mean_ms": (item["metrics"].get("planner_latency_mean_ms") or {}).get("mean"),
            }
        )

    parts = [
        "# Incremental Metrics Summary",
        "",
        f"- Generated at (UTC): {summary['generated_at_utc']}",
        f"- Sample count: {summary['sample_count']}",
        f"- Error rows: {summary['error_rows']}",
        "",
        "## Overall",
        "",
        markdown_table(
            overall_rows,
            [
                ("Metric", "metric"),
                ("Count", "count"),
                ("Mean/Rate", "mean_or_rate"),
                ("P50", "p50"),
                ("P95", "p95"),
            ],
        ),
        "## By Diagram Type",
        "",
        markdown_table(
            by_type_rows,
            [
                ("Diagram Type", "diagram_type"),
                ("Count", "count"),
                ("Final Match Rate", "final_match_rate"),
                ("Canonicalized Match Rate", "canonicalized_match_rate"),
                ("Entity Semantic F1 Mean", "entity_semantic_f1_mean"),
                ("Coverage Mean", "coverage_mean"),
                ("Planner Latency Mean Ms", "planner_latency_mean_ms"),
            ],
        ),
    ]
    return "\n".join(parts).strip() + "\n"


def _normalize_graph_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _split_graph_tokens(text: str) -> tuple[str, ...]:
    raw = (text or "").strip()
    if not raw:
        return ()
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    raw = raw.replace("/", " ").replace("_", " ").replace("-", " ")
    tokens = [token.lower() for token in re.findall(r"[A-Za-z]+|[0-9]+", raw)]
    tokens = [token for token in tokens if token and token not in STRUCTURAL_STOPWORDS]
    return tuple(tokens)


def _looks_like_generic_identifier(text: str) -> bool:
    normalized = _normalize_graph_text(text)
    if not normalized:
        return True
    return bool(
        re.fullmatch(
            r"(node|group|edge|participant|actor|cluster|subgraph|n|g|e)[0-9]*",
            normalized,
        )
    )


def _semantic_tokens(label: str, identifier: str) -> tuple[str, ...]:
    label_tokens = _split_graph_tokens(label)
    if label_tokens:
        return label_tokens
    if not _looks_like_generic_identifier(identifier):
        identifier_tokens = _split_graph_tokens(identifier)
        if identifier_tokens:
            return identifier_tokens
    normalized_identifier = _normalize_graph_text(identifier)
    return (normalized_identifier,) if normalized_identifier else ()


def _tokens_signature(tokens: tuple[str, ...]) -> str:
    return "|".join(sorted(set(tokens)))


def _token_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    left_set = set(left)
    right_set = set(right)
    overlap = len(left_set & right_set)
    if overlap <= 0:
        return 0.0
    precision = overlap / len(left_set)
    recall = overlap / len(right_set)
    return round((2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0, 6)


def _pair_similarity(
    left: tuple[tuple[str, ...], tuple[str, ...]],
    right: tuple[tuple[str, ...], tuple[str, ...]],
) -> float:
    return round(
        (_token_similarity(left[0], right[0]) + _token_similarity(left[1], right[1])) / 2.0,
        6,
    )


def _edge_similarity(
    left: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    right: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
) -> float:
    parts = [
        _token_similarity(left[0], right[0]),
        _token_similarity(left[1], right[1]),
    ]
    if left[2] or right[2]:
        parts.append(_token_similarity(left[2], right[2]))
    return round(sum(parts) / len(parts), 6) if parts else 0.0


def _counter_overlap_f1(pred: Counter[str], ref: Counter[str]) -> float:
    pred_total = sum(pred.values())
    ref_total = sum(ref.values())
    if pred_total == 0 and ref_total == 0:
        return 1.0
    if pred_total == 0 or ref_total == 0:
        return 0.0
    overlap = sum((pred & ref).values())
    precision = overlap / pred_total
    recall = overlap / ref_total
    return round((2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0, 4)


def _soft_f1(pred_items: list[Any], ref_items: list[Any], similarity_fn, threshold: float = 0.5) -> float:
    if not pred_items and not ref_items:
        return 1.0
    if not pred_items or not ref_items:
        return 0.0
    candidates: list[tuple[float, int, int]] = []
    for pred_index, pred_item in enumerate(pred_items):
        for ref_index, ref_item in enumerate(ref_items):
            score = float(similarity_fn(pred_item, ref_item))
            if score >= threshold:
                candidates.append((score, pred_index, ref_index))
    if not candidates:
        return 0.0
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    matched_pred: set[int] = set()
    matched_ref: set[int] = set()
    matched_weight = 0.0
    for score, pred_index, ref_index in candidates:
        if pred_index in matched_pred or ref_index in matched_ref:
            continue
        matched_pred.add(pred_index)
        matched_ref.add(ref_index)
        matched_weight += score
    precision = matched_weight / len(pred_items)
    recall = matched_weight / len(ref_items)
    return round((2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0, 4)


def _graph_semantic_items(graph_ir: GraphIR) -> dict[str, Any]:
    node_tokens_by_id = {
        node.id: _semantic_tokens(node.label, node.id)
        for node in graph_ir.nodes
    }
    group_tokens_by_id = {
        group.id: _semantic_tokens(group.label, group.id)
        for group in graph_ir.groups
    }
    lookup = {**group_tokens_by_id, **node_tokens_by_id}

    def resolve_tokens(identifier: str) -> tuple[str, ...]:
        if identifier in lookup:
            return lookup[identifier]
        return _semantic_tokens("", identifier)

    node_items = list(node_tokens_by_id.values())
    group_items = list(group_tokens_by_id.values())
    edge_items = [
        (
            resolve_tokens(edge.source),
            resolve_tokens(edge.target),
            _semantic_tokens(edge.label, edge.id),
        )
        for edge in graph_ir.edges
    ]
    attachment_items: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for node in graph_ir.nodes:
        if isinstance(node.parent, str) and node.parent:
            attachment_items.append((node_tokens_by_id[node.id], resolve_tokens(node.parent)))
    for group in graph_ir.groups:
        if isinstance(group.parent, str) and group.parent:
            attachment_items.append((group_tokens_by_id[group.id], resolve_tokens(group.parent)))

    node_counter = Counter(_tokens_signature(item) for item in node_items)
    group_counter = Counter(_tokens_signature(item) for item in group_items)
    edge_counter = Counter(
        f"{_tokens_signature(source)}->{_tokens_signature(target)}|{_tokens_signature(label)}"
        for source, target, label in edge_items
    )
    return {
        "node_items": node_items,
        "group_items": group_items,
        "edge_items": edge_items,
        "attachment_items": attachment_items,
        "node_counter": node_counter,
        "group_counter": group_counter,
        "edge_counter": edge_counter,
    }


def _load_predicted_graph(detail_path: str) -> GraphIR | None:
    if not detail_path:
        return None
    path = resolve_path(detail_path)
    if not path.exists():
        return None
    payload = read_json(path)
    graph_payload = (((payload.get("final_state") or {}).get("current_graph_ir")) or {})
    if not isinstance(graph_payload, dict) or not graph_payload:
        return None
    return _graph_ir_from_payload(graph_payload)


def _enrich_row_with_graph_metrics(
    row: dict[str, Any],
    run_root: str,
    sample_cache: dict[str, GraphIR],
) -> dict[str, Any]:
    if row.get("error"):
        return row

    predicted_graph = _load_predicted_graph(str(row.get("detail_path", "")))
    sample_id = str(row.get("sample_id", ""))
    if not sample_id:
        return row
    if sample_id not in sample_cache:
        sample_cache[sample_id] = load_runtime_sample(run_root, sample_id).stages[-1].graph_ir
    reference_graph = sample_cache[sample_id]
    if predicted_graph is None:
        enriched = dict(row)
        for field in (
            "canonicalized_match",
            "node_semantic_f1",
            "group_semantic_f1",
            "edge_semantic_f1",
            "attachment_semantic_f1",
            "entity_semantic_f1",
        ):
            enriched[field] = None
        return enriched

    pred_items = _graph_semantic_items(predicted_graph)
    ref_items = _graph_semantic_items(reference_graph)
    node_f1 = _soft_f1(pred_items["node_items"], ref_items["node_items"], _token_similarity)
    group_f1 = _soft_f1(pred_items["group_items"], ref_items["group_items"], _token_similarity)
    edge_f1 = _soft_f1(pred_items["edge_items"], ref_items["edge_items"], _edge_similarity)
    attachment_f1 = _soft_f1(pred_items["attachment_items"], ref_items["attachment_items"], _pair_similarity)

    weighted_scores: list[tuple[float, int]] = []
    for score, pred_items_key, ref_items_key in (
        (node_f1, "node_items", "node_items"),
        (group_f1, "group_items", "group_items"),
        (edge_f1, "edge_items", "edge_items"),
        (attachment_f1, "attachment_items", "attachment_items"),
    ):
        weight = max(len(pred_items[pred_items_key]), len(ref_items[ref_items_key]))
        if weight > 0:
            weighted_scores.append((score, weight))
    entity_f1 = round(
        sum(score * weight for score, weight in weighted_scores) / sum(weight for _, weight in weighted_scores),
        4,
    ) if weighted_scores else 1.0

    canonicalized_match = (
        pred_items["node_counter"] == ref_items["node_counter"]
        and pred_items["group_counter"] == ref_items["group_counter"]
        and pred_items["edge_counter"] == ref_items["edge_counter"]
    )

    return {
        **row,
        "canonicalized_match": canonicalized_match,
        "node_semantic_f1": node_f1,
        "group_semantic_f1": group_f1,
        "edge_semantic_f1": edge_f1,
        "attachment_semantic_f1": attachment_f1,
        "entity_semantic_f1": entity_f1,
    }


def main() -> None:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(resolve_path(args.input_jsonl))
    sample_cache: dict[str, GraphIR] = {}
    rows = [_enrich_row_with_graph_metrics(row, args.run_root, sample_cache) for row in rows]
    valid_rows = [row for row in rows if not row.get("error")]

    summary = {
        "generated_at_utc": utc_iso(),
        "input_jsonl": str(resolve_path(args.input_jsonl)),
        "reference_run_root": str(resolve_path(args.run_root)),
        "sample_count": len(rows),
        "valid_row_count": len(valid_rows),
        "error_rows": len(rows) - len(valid_rows),
        "overall": aggregate_rows(valid_rows, INCREMENTAL_METRIC_FIELDS),
        "slices": {
            "by_diagram_type": group_rows(valid_rows, "diagram_type", INCREMENTAL_METRIC_FIELDS),
            "by_split": group_rows(valid_rows, "split", INCREMENTAL_METRIC_FIELDS),
        },
        "failure_examples": top_failure_examples(valid_rows, "stage_coverage_rate", limit=20),
        "semantic_failure_examples": top_failure_examples(valid_rows, "entity_semantic_f1", limit=20),
    }

    summary_path = output_dir / "incremental_metrics.summary.json"
    markdown_path = output_dir / "incremental_metrics.summary.md"
    csv_path = output_dir / "incremental_metrics.detail.csv"

    write_json(summary_path, summary)
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")
    write_csv(csv_path, rows, fieldnames=sorted({key for row in rows for key in row.keys()}))

    print(f"Summary: {summary_path}")
    print(f"Markdown: {markdown_path}")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
