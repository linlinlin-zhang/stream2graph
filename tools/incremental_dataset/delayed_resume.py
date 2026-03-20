#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sleep for a while, then resume the incremental dataset build.")
    parser.add_argument("--delay-seconds", type=int, required=True)
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--run-name", type=str, required=True)
    parser.add_argument("--stdout-log", type=str, required=True)
    parser.add_argument("--stderr-log", type=str, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    time.sleep(max(0, int(args.delay_seconds)))

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "incremental_dataset" / "run_full_build.py"
    stdout_path = Path(args.stdout_log)
    stderr_path = Path(args.stderr_log)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    with stdout_path.open("a", encoding="utf-8") as stdout_handle, stderr_path.open("a", encoding="utf-8") as stderr_handle:
        subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--config",
                args.config,
                "--run-name",
                args.run_name,
            ],
            cwd=str(repo_root),
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )


if __name__ == "__main__":
    main()
