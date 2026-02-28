#!/usr/bin/env python3
"""Generate a timestamped change report for current repo working tree."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def safe_run(cmd: list[str]) -> str:
    try:
        return run(cmd)
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--auto-add", action="store_true")
    parser.add_argument("--title", default="Automated Change Report")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    ts = datetime.now(timezone.utc)
    ts_tag = ts.strftime("%Y%m%d_%H%M%S")
    ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    branch = safe_run(["git", "-C", str(repo), "branch", "--show-current"])
    head = safe_run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"]) or "<no-commit>"

    status = safe_run(["git", "-C", str(repo), "status", "--porcelain"]).splitlines()
    changed = []
    for line in status:
        if not line.strip():
            continue
        code = line[:2]
        path = line[3:]
        changed.append((code, path))

    ext_counter = Counter()
    for _, path in changed:
        ext = Path(path).suffix.lower() or "<noext>"
        ext_counter[ext] += 1

    out_dir = repo / "reports" / "change_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"CHANGE_REPORT_{ts_tag}.md"
    json_path = out_dir / f"CHANGE_REPORT_{ts_tag}.json"

    payload = {
        "generated_at_utc": ts_iso,
        "branch": branch,
        "head": head,
        "changed_file_count": len(changed),
        "by_extension": dict(ext_counter.most_common()),
        "changed_files": [{"status": c, "path": p} for c, p in changed],
    }

    md_lines = [
        f"# {args.title}",
        "",
        f"- Generated at (UTC): {ts_iso}",
        f"- Branch: `{branch}`",
        f"- HEAD: `{head}`",
        f"- Changed files: {len(changed)}",
        "",
        "## Changed Files by Extension",
        "",
    ]

    if ext_counter:
        for ext, count in ext_counter.most_common():
            md_lines.append(f"- `{ext}`: {count}")
    else:
        md_lines.append("- (no changes detected)")

    md_lines.extend(["", "## Changed Files", ""])
    if changed:
        for code, path in changed:
            md_lines.append(f"- `{code}` {path}")
    else:
        md_lines.append("- (clean working tree)")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_md = out_dir / "CHANGE_REPORT_LATEST.md"
    latest_json = out_dir / "CHANGE_REPORT_LATEST.json"
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(str(md_path))

    if args.auto_add:
        subprocess.check_call(["git", "-C", str(repo), "add", str(md_path), str(json_path), str(latest_md), str(latest_json)])


if __name__ == "__main__":
    main()
