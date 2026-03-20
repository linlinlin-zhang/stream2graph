from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DatasetVersion


def _split_count(split_path: Path) -> int:
    if not split_path.exists():
        return 0
    payload = json.loads(split_path.read_text(encoding="utf-8"))
    return int(payload.get("count", len(payload.get("ids", []))))


def discover_dataset_versions() -> list[dict[str, Any]]:
    settings = get_settings()
    root = settings.dataset_root
    if not root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for dataset_dir in sorted(root.iterdir()):
        if not dataset_dir.is_dir():
            continue
        split_dir = dataset_dir / "splits"
        if not split_dir.exists():
            continue
        slug = dataset_dir.name
        rows.append(
            {
                "slug": slug,
                "display_name": slug.replace("_", " "),
                "dataset_dir": str(dataset_dir),
                "split_dir": str(split_dir),
                "sample_count": len(list(dataset_dir.glob("*.json"))),
                "train_count": _split_count(split_dir / "train_ids.json"),
                "validation_count": _split_count(split_dir / "validation_ids.json"),
                "test_count": _split_count(split_dir / "test_ids.json"),
                "is_default": slug == settings.default_dataset_version,
                "meta_json": {
                    "kind": "dataset_release",
                },
            }
        )
    return rows


def sync_dataset_versions(db: Session) -> None:
    existing = {item.slug: item for item in db.scalars(select(DatasetVersion)).all()}
    discovered = discover_dataset_versions()
    for row in discovered:
        obj = existing.get(row["slug"])
        if obj is None:
            obj = DatasetVersion(**row)
            db.add(obj)
            continue
        obj.display_name = row["display_name"]
        obj.dataset_dir = row["dataset_dir"]
        obj.split_dir = row["split_dir"]
        obj.sample_count = row["sample_count"]
        obj.train_count = row["train_count"]
        obj.validation_count = row["validation_count"]
        obj.test_count = row["test_count"]
        obj.is_default = row["is_default"]
        obj.meta_json = row["meta_json"]
    for slug, obj in existing.items():
        if slug not in {row["slug"] for row in discovered}:
            db.delete(obj)
    db.commit()


def get_dataset_version_or_404(db: Session, slug: str) -> DatasetVersion:
    obj = db.scalar(select(DatasetVersion).where(DatasetVersion.slug == slug))
    if obj is None:
        raise ValueError(f"dataset version not found: {slug}")
    return obj


def list_split_ids(dataset: DatasetVersion, split: str) -> list[str]:
    split_path = Path(dataset.split_dir) / f"{split}_ids.json"
    if not split_path.exists():
        raise ValueError(f"split not found: {split}")
    payload = json.loads(split_path.read_text(encoding="utf-8"))
    return [str(item) for item in payload.get("ids", [])]


def list_split_summary(dataset: DatasetVersion) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ("train", "validation", "test"):
        ids = list_split_ids(dataset, split)
        rows.append(
            {
                "split": split,
                "count": len(ids),
                "example_ids": ids[:5],
            }
        )
    return rows


def list_samples(dataset: DatasetVersion, split: str, *, search: str = "", offset: int = 0, limit: int = 25) -> list[dict[str, Any]]:
    ids = list_split_ids(dataset, split)
    if search:
        lowered = search.lower()
        ids = [item for item in ids if lowered in item.lower()]
    selected = ids[offset : offset + limit]
    rows: list[dict[str, Any]] = []
    for sample_id in selected:
        sample_path = Path(dataset.dataset_dir) / f"{sample_id}.json"
        if not sample_path.exists():
            continue
        raw = json.loads(sample_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "sample_id": sample_id,
                "diagram_type": str(raw.get("diagram_type", "unknown")),
                "dialogue_turns": len(raw.get("cscw_dialogue", [])),
                "compilation_status": raw.get("compilation_status"),
                "release_version": raw.get("release_version"),
                "license_name": raw.get("license_name") or raw.get("license"),
            }
        )
    return rows


def get_sample_detail(dataset: DatasetVersion, split: str, sample_id: str) -> dict[str, Any]:
    if sample_id not in set(list_split_ids(dataset, split)):
        raise ValueError(f"sample not in split: {sample_id}")
    sample_path = Path(dataset.dataset_dir) / f"{sample_id}.json"
    if not sample_path.exists():
        raise ValueError(f"sample not found: {sample_id}")
    raw = json.loads(sample_path.read_text(encoding="utf-8"))
    return {
        "dataset_version": dataset.slug,
        "split": split,
        "sample_id": sample_id,
        "diagram_type": str(raw.get("diagram_type", "unknown")),
        "code": str(raw.get("code", "")),
        "dialogue": raw.get("cscw_dialogue", []),
        "metadata": {
            key: value
            for key, value in raw.items()
            if key not in {"code", "cscw_dialogue"}
        },
    }
