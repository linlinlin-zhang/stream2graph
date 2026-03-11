#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import resolve_path, slugify, utc_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export selected evaluation outputs into a git-trackable bundle.")
    parser.add_argument("--bundle-name", type=str, required=True)
    parser.add_argument("--published-dir", type=str, default="reports/evaluation/published")
    parser.add_argument(
        "--entry",
        action="append",
        default=[],
        help="Copy mapping in the form label=path. Repeat for multiple files or directories.",
    )
    parser.add_argument("--notes", type=str, default="")
    return parser.parse_args()


def export_entries(bundle_name: str, published_dir: str | Path, entries: list[tuple[str, Path]], notes: str = "") -> Path:
    root = resolve_path(published_dir)
    bundle_dir = root / slugify(bundle_name)
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_entries: list[dict[str, str]] = []
    for label, source in entries:
        if not source.exists():
            continue
        target_base = bundle_dir / slugify(label)
        if source.is_dir():
            shutil.copytree(source, target_base)
            destination = target_base
        else:
            target_base.mkdir(parents=True, exist_ok=True)
            destination = target_base / source.name
            shutil.copy2(source, destination)
        copied_entries.append(
            {
                "label": label,
                "source": str(source),
                "destination": str(destination),
            }
        )

    manifest = {
        "generated_at_utc": utc_iso(),
        "bundle_name": bundle_name,
        "bundle_dir": str(bundle_dir),
        "notes": notes,
        "entries": copied_entries,
    }
    write_json(bundle_dir / "bundle_manifest.json", manifest)
    return bundle_dir


def main() -> None:
    args = parse_args()
    parsed_entries: list[tuple[str, Path]] = []
    for raw_entry in args.entry:
        if "=" not in raw_entry:
            raise SystemExit(f"Invalid entry '{raw_entry}'. Expected label=path.")
        label, raw_path = raw_entry.split("=", 1)
        parsed_entries.append((label.strip(), resolve_path(raw_path.strip())))

    bundle_dir = export_entries(
        bundle_name=args.bundle_name,
        published_dir=args.published_dir,
        entries=parsed_entries,
        notes=args.notes,
    )
    print(bundle_dir)


if __name__ == "__main__":
    main()
