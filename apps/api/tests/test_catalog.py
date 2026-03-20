from __future__ import annotations

from pathlib import Path

from app.services.catalog import discover_dataset_versions


def test_catalog_discovers_default_dataset() -> None:
    rows = discover_dataset_versions()
    assert rows
    assert any(item["slug"] == "release_v7_kimi_k25_fullregen_strict_20260313" for item in rows)
    assert all(Path(item["dataset_dir"]).exists() for item in rows)
