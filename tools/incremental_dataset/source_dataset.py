from __future__ import annotations

import json
from pathlib import Path

from tools.eval.common import read_json, resolve_path
from tools.eval.metrics import canonical_diagram_type
from tools.incremental_dataset.schema import SourceSample


DEFAULT_SOURCE_DIR = (
    "versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/"
    "release_v7_kimi_k25_fullregen_strict_20260313"
)
DEFAULT_SPLIT_DIR = f"{DEFAULT_SOURCE_DIR}/splits"
DEFAULT_DIAGRAM_TYPES = (
    "flowchart",
    "architecture",
    "sequence",
    "statediagram",
    "er",
    "mindmap",
)


def load_split_map(split_dir: str | Path) -> dict[str, list[str]]:
    split_dir = resolve_path(split_dir)
    payloads = {
        "train": read_json(split_dir / "train_ids.json"),
        "validation": read_json(split_dir / "validation_ids.json"),
        "test": read_json(split_dir / "test_ids.json"),
    }
    return {split: [str(sample_id) for sample_id in payload["ids"]] for split, payload in payloads.items()}


def load_source_samples(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    split_dir: str | Path = DEFAULT_SPLIT_DIR,
    diagram_types: tuple[str, ...] | list[str] | None = None,
) -> list[SourceSample]:
    source_dir = resolve_path(source_dir)
    diagram_type_filter = {canonical_diagram_type(item) for item in (diagram_types or DEFAULT_DIAGRAM_TYPES)}
    split_map = load_split_map(split_dir)
    rows: list[SourceSample] = []

    for split_name in ("train", "validation", "test"):
        for sample_id in split_map.get(split_name, []):
            path = source_dir / f"{sample_id}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            diagram_type = canonical_diagram_type(str(payload.get("diagram_type", "")))
            if diagram_type_filter and diagram_type not in diagram_type_filter:
                continue
            rows.append(
                SourceSample(
                    sample_id=sample_id,
                    split=split_name,
                    diagram_type=diagram_type,
                    code=str(payload.get("code", "")),
                    source_path=str(path),
                    source=str(payload.get("source", "")),
                    license=str(payload.get("license", "")),
                    compilation_status=str(payload.get("compilation_status", "")),
                    content_size=int(payload.get("content_size", 0) or 0),
                    metadata={
                        "source_url": payload.get("source_url"),
                        "github_repo": payload.get("github_repo"),
                        "github_file_path": payload.get("github_file_path"),
                        "release_version": payload.get("release_version"),
                        "release_built_at": payload.get("release_built_at"),
                    },
                )
            )
    return rows
