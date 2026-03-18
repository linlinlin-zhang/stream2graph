#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import resolve_path, write_json
from tools.incremental_dataset.progress import build_agent_progress_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize agent build progress for an incremental dataset run.")
    parser.add_argument("--agent-dir", type=str, required=True)
    parser.add_argument("--output", type=str, default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent_dir = resolve_path(args.agent_dir)
    output_path = resolve_path(args.output) if args.output else agent_dir.parent / "progress_report.json"
    payload = build_agent_progress_report(agent_dir)
    write_json(output_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
