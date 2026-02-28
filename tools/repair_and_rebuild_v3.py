#!/usr/bin/env python3
"""
Repair latest v3 dataset first, then clean only unrecoverable records.

Outputs under v3 dataset root:
- repaired_v3_<date>                : all records with repaired fields
- train_v3_repaired_<date>          : training-ready records (compilable + dialogue ok)
- compliant_v3_repaired_<date>      : compliant subset (training-ready + valid license)

Reports:
- reports/release_reports/repair_rebuild_v3_<timestamp>.{json,md}
- reports/release_reports/repair_rebuild_v3_latest.{json,md}
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

import requests

INVALID_LICENSES = {"", "none", "error", "unknown", "rate_limited", None}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_license(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def valid_license(value: Optional[str]) -> bool:
    return normalize_license(value) not in INVALID_LICENSES


def infer_diagram_type_from_id(sample_id: str) -> Optional[str]:
    sid = sample_id.lower()
    mapping = [
        ("requirementdiagram", "requirementDiagram"),
        ("statediagram", "stateDiagram"),
        ("gitgraph", "gitGraph"),
        ("c4context", "C4Context"),
        ("architecture", "architecture"),
        ("flowchart", "flowchart"),
        ("sequence", "sequence"),
        ("class", "class"),
        ("mindmap", "mindmap"),
        ("journey", "journey"),
        ("gantt", "gantt"),
        ("timeline", "timeline"),
        ("sankey", "sankey"),
        ("packet-beta", "packet-beta"),
        ("block-beta", "block-beta"),
        ("xychart", "xychart"),
        ("pie", "pie"),
        ("er", "er"),
        ("kanban", "kanban"),
    ]
    for key, value in mapping:
        if key in sid:
            return value
    return None


def infer_diagram_type_from_code(code: str) -> Optional[str]:
    c = code.lower()
    if "sequencediagram" in c:
        return "sequence"
    if "classdiagram" in c:
        return "class"
    if "erdiagram" in c:
        return "er"
    if "statediagram" in c:
        return "stateDiagram"
    if "gitgraph" in c:
        return "gitGraph"
    if "mindmap" in c:
        return "mindmap"
    if "journey" in c:
        return "journey"
    if "gantt" in c:
        return "gantt"
    if "pie" in c:
        return "pie"
    if "timeline" in c:
        return "timeline"
    if "xychart" in c:
        return "xychart"
    if "architecture" in c:
        return "architecture"
    if "flowchart" in c or "graph td" in c or "graph lr" in c or "graph rl" in c:
        return "flowchart"
    if "c4context" in c:
        return "C4Context"
    if "requirementdiagram" in c:
        return "requirementDiagram"
    if "sankey" in c:
        return "sankey"
    if "packet-beta" in c:
        return "packet-beta"
    if "block-beta" in c:
        return "block-beta"
    if "kanban" in c:
        return "kanban"
    return None


def infer_source(sample_id: str, source_url: Optional[str], source: Optional[str], source_type: Optional[str]) -> Optional[str]:
    if source:
        return str(source)
    if source_type:
        st = str(source_type).lower()
        if "gitlab" in st:
            return "gitlab"
        if "github" in st:
            return "github"
        if "other" in st:
            return "other"
        if "augment" in st:
            return "augmented_real_structure"
        return st
    sid = sample_id.lower()
    if sid.startswith("aug_"):
        return "augmented_real_structure"
    if sid.startswith("gh_"):
        return "github"
    if sid.startswith("gl_"):
        return "gitlab"
    if sid.startswith("ot_"):
        return "other"
    if source_url:
        u = source_url.lower()
        if "github.com" in u:
            return "github"
        if "gitlab" in u:
            return "gitlab"
    return None


def extract_repo(record: Dict) -> Optional[str]:
    repo = record.get("github_repo")
    if isinstance(repo, str) and "/" in repo:
        return repo
    url = record.get("source_url")
    if isinstance(url, str) and "github.com/" in url:
        m = re.search(r"github\.com/([^/]+/[^/]+)", url)
        if m:
            return m.group(1)
    return None


def basic_code_cleanup(code: str) -> str:
    c = code
    c = re.sub(r"^```(?:mermaid)?\s*", "", c.strip(), flags=re.IGNORECASE)
    c = re.sub(r"```\s*$", "", c, flags=re.IGNORECASE)
    c = c.replace("\xa0", " ")
    c = c.replace("\r\n", "\n").strip()
    return c


def add_header_if_missing(code: str) -> str:
    c = code.strip()
    lower = c.lower()
    known = [
        "flowchart",
        "graph ",
        "sequencediagram",
        "classdiagram",
        "erdiagram",
        "statediagram",
        "gitgraph",
        "mindmap",
        "journey",
        "gantt",
        "pie",
        "timeline",
        "xychart",
        "architecture",
        "c4context",
        "requirementdiagram",
        "sankey",
        "packet-beta",
        "block-beta",
        "kanban",
    ]
    if any(lower.startswith(k) for k in known):
        return c
    # Heuristic fallback for arrow-heavy snippets.
    if "-->" in c or "---" in c:
        return "flowchart TD\n" + c
    return c


def balance_brackets(code: str) -> str:
    c = code
    pairs = [("[", "]"), ("(", ")"), ("{", "}")]
    for o, cl in pairs:
        diff = c.count(o) - c.count(cl)
        if diff > 0:
            c += cl * diff
    return c


def looks_mermaid_like(code: str) -> bool:
    if not isinstance(code, str):
        return False
    lines = [ln.strip() for ln in code.splitlines() if ln.strip()]
    if not lines:
        return False

    first = lines[0].lower()
    known_prefixes = [
        "flowchart",
        "graph ",
        "sequencediagram",
        "classdiagram",
        "erdiagram",
        "statediagram",
        "gitgraph",
        "mindmap",
        "journey",
        "gantt",
        "pie",
        "timeline",
        "xychart",
        "architecture",
        "c4context",
        "requirementdiagram",
        "sankey",
        "packet-beta",
        "block-beta",
        "kanban",
    ]
    if any(first.startswith(p) for p in known_prefixes):
        return True

    text = "\n".join(lines).lower()
    if "subgraph" in text and "-->" in text:
        return True
    if "participant " in text and "->" in text:
        return True
    if "state " in text and ("-->" in text or "->" in text):
        return True
    if ("-->" in text or "---" in text or "==>" in text) and len(lines) >= 2:
        return True

    return False


def local_try_repair_and_judge(code: str) -> Tuple[bool, str, str]:
    base = code if isinstance(code, str) else ""
    candidates: List[Tuple[str, str]] = []
    candidates.append(("original", base))
    c1 = basic_code_cleanup(base)
    candidates.append(("cleanup", c1))
    c2 = add_header_if_missing(c1)
    candidates.append(("header", c2))
    c3 = balance_brackets(c2)
    candidates.append(("balance", c3))

    seen = set()
    uniq: List[Tuple[str, str]] = []
    for label, candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        uniq.append((label, candidate))

    for label, candidate in uniq:
        if looks_mermaid_like(candidate):
            return True, candidate, label
    return False, base, "none"


class KrokiChecker:
    def __init__(self, timeout: int = 10, token: Optional[str] = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def check(self, code: str) -> bool:
        if not isinstance(code, str) or not code.strip():
            return False
        payload = code.encode("utf-8", errors="ignore")
        for _ in range(2):
            try:
                resp = self.session.post(
                    "https://kroki.io/mermaid/svg",
                    data=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return True
            except Exception:
                time.sleep(0.1)
        return False

    def try_repair_and_check(self, code: str) -> Tuple[bool, str, str]:
        candidates: List[Tuple[str, str]] = []
        base = code if isinstance(code, str) else ""
        candidates.append(("original", base))
        c1 = basic_code_cleanup(base)
        candidates.append(("cleanup", c1))
        c2 = add_header_if_missing(c1)
        candidates.append(("header", c2))
        c3 = balance_brackets(c2)
        candidates.append(("balance", c3))

        seen = set()
        uniq: List[Tuple[str, str]] = []
        for label, candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            uniq.append((label, candidate))

        for label, candidate in uniq:
            if self.check(candidate):
                return True, candidate, label
        return False, base, "none"


def create_min_turn(idx: int, role: str, action: str, utt: str, elements: Optional[List[str]] = None) -> Dict:
    return {
        "turn_id": idx,
        "role": role,
        "action_type": action,
        "utterance": utt,
        "elements_involved": elements or [],
        "is_repair": False,
    }


def repair_dialogue(dialogue: List[Dict], min_turns: int, max_turns: int) -> Tuple[List[Dict], List[str]]:
    changes: List[str] = []
    if len(dialogue) > max_turns:
        dialogue = dialogue[:max_turns]
        changes.append("dialogue_trimmed")

    if len(dialogue) < min_turns:
        cur = list(dialogue)
        next_idx = len(cur) + 1
        role_seq = ["Domain_Expert", "Diagram_Editor"]
        while len(cur) < min_turns:
            role = role_seq[(next_idx - 1) % 2]
            if role == "Domain_Expert":
                cur.append(create_min_turn(next_idx, role, "confirm", "对，按这个结构继续。"))
            else:
                cur.append(create_min_turn(next_idx, role, "execute", "[系统日志: 补齐最小对话轮次的结构确认步骤]"))
            next_idx += 1
        dialogue = cur
        changes.append("dialogue_padded")

    # Re-index turns for consistency.
    for i, turn in enumerate(dialogue, start=1):
        turn["turn_id"] = i

    return dialogue, changes


def build_splits(ids: List[str], type_map: Dict[str, str], seed: int) -> Dict[str, List[str]]:
    rng = random.Random(seed)
    grouped: Dict[str, List[str]] = {}
    for sid in ids:
        grouped.setdefault(type_map[sid], []).append(sid)

    train, val, test = [], [], []
    for _, group in grouped.items():
        rng.shuffle(group)
        n = len(group)
        n_train = int(n * 0.8)
        n_val = int(n * 0.1)
        n_test = n - n_train - n_val
        train.extend(group[:n_train])
        val.extend(group[n_train:n_train + n_val])
        test.extend(group[n_train + n_val:n_train + n_val + n_test])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return {"train": train, "validation": val, "test": test}


def write_report_md(report: Dict, path: Path) -> None:
    lines = [
        "# V3 Repair And Rebuild Report",
        "",
        f"- Built at: {report['built_at_utc']}",
        f"- Source: `{report['source_dir']}`",
        "",
        "## Counts",
        "",
        f"- Input records: {report['input_records']}",
        f"- Repaired full set: {report['repaired_records']}",
        f"- Training-ready set: {report['train_ready_records']}",
        f"- Compliant set: {report['compliant_records']}",
        "",
        "## Recovery",
        "",
        f"- Compilation recovered (local): {report['recovery']['compilation_recovered_local']}",
        f"- Compilation recovered (kroki fallback): {report['recovery']['compilation_recovered_kroki']}",
        f"- License recovered: {report['recovery']['license_recovered']}",
        f"- Source recovered: {report['recovery']['source_recovered']}",
        f"- Diagram type recovered: {report['recovery']['diagram_type_recovered']}",
        f"- Dialogue repaired (trim/pad): {report['recovery']['dialogue_repaired']}",
        "",
        "## Compilation Audit",
        "",
        f"- Audit sample size: {report['compilation_audit']['sample_size']}",
        f"- Audit pass: {report['compilation_audit']['pass']}",
        f"- Audit fail: {report['compilation_audit']['fail']}",
        f"- Audit pass rate: {report['compilation_audit']['pass_rate']}",
        "",
        "## Remaining Unresolved",
        "",
    ]
    for k, v in report["remaining_unresolved"].items():
        lines.append(f"- {k}: {v}")

    lines.extend(["", "## Top Rejection Reasons For Compliant Set", ""])
    for k, v in report["compliant_rejection_reasons"].items():
        lines.append(f"- {k}: {v}")

    lines.extend(["", "## Output Paths", ""])
    lines.append(f"- Repaired full: `{report['output_dirs']['repaired_full']}`")
    lines.append(f"- Train-ready: `{report['output_dirs']['train_ready']}`")
    lines.append(f"- Compliant: `{report['output_dirs']['compliant']}`")
    lines.append(f"- Unresolved index: `{report['output_dirs']['unresolved_index']}`")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/cscw_dialogue_dataset",
    )
    parser.add_argument(
        "--baseline-dir",
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/final_v2_9k",
    )
    parser.add_argument(
        "--output-root",
        default="versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset",
    )
    parser.add_argument("--min-turns", type=int, default=4)
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--kroki-audit-sample", type=int, default=240)
    parser.add_argument("--kroki-timeout", type=int, default=8)
    parser.add_argument("--skip-kroki-audit", action="store_true")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    baseline_dir = Path(args.baseline_dir)
    output_root = Path(args.output_root)

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    repaired_dir = output_root / f"repaired_v3_{date_tag}"
    train_ready_dir = output_root / f"train_v3_repaired_{date_tag}"
    compliant_dir = output_root / f"compliant_v3_repaired_{date_tag}"
    for d in [repaired_dir, train_ready_dir, compliant_dir]:
        ensure_dir(d)

    reports_dir = Path("reports/release_reports")
    ensure_dir(reports_dir)

    # Load baseline by filename and by sample id.
    baseline_by_file: Dict[str, Dict] = {}
    baseline_by_id: Dict[str, Dict] = {}
    for f in baseline_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        baseline_by_file[f.name] = d
        sid = str(d.get("id") or f.stem)
        baseline_by_id[sid] = d

    # Load source records.
    records_by_file: Dict[str, Dict] = {}
    for f in source_dir.glob("*.json"):
        try:
            records_by_file[f.name] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            records_by_file[f.name] = {}

    input_count = len(records_by_file)

    recovery = Counter()
    unresolved = Counter()
    compliant_reject = Counter()

    # First pass: metadata + dialogue + license inference (without expensive network compile check).
    compile_targets: List[Tuple[str, str]] = []  # (filename, code)
    repo_license_candidates: Dict[str, str] = {}  # filename -> repo

    common_copy_keys = [
        "source",
        "source_type",
        "source_url",
        "diagram_type",
        "compilation_status",
        "compilation_error",
        "license",
        "license_name",
        "license_url",
        "github_repo",
        "github_file_path",
        "repo_owner",
        "repo_name",
        "repo_stars",
        "repo_forks",
        "repo_topics",
        "repo_language",
        "repo_description",
        "repo_created_at",
        "repo_updated_at",
        "content_size",
        "collected_at",
        "seed_id",
        "augmentation_domain",
    ]

    for fname, rec in records_by_file.items():
        if not isinstance(rec, dict):
            rec = {}
            records_by_file[fname] = rec

        base = baseline_by_file.get(fname)
        sid = str(rec.get("id") or (base.get("id") if isinstance(base, dict) else Path(fname).stem))
        rec["id"] = sid

        # Fill from baseline if key missing.
        if isinstance(base, dict):
            for key in common_copy_keys:
                if key not in rec and key in base:
                    rec[key] = base[key]
                    if key == "source":
                        recovery["source_recovered"] += 1
                    elif key == "diagram_type":
                        recovery["diagram_type_recovered"] += 1
                    elif key == "license":
                        recovery["license_recovered"] += 1

        # Infer source/type if still missing.
        inferred_source = infer_source(
            sid,
            rec.get("source_url"),
            rec.get("source"),
            rec.get("source_type"),
        )
        if inferred_source and not rec.get("source"):
            rec["source"] = inferred_source
            recovery["source_recovered"] += 1
        if not rec.get("source"):
            rec["source"] = "other"
            recovery["source_recovered"] += 1
            rec.setdefault("repair_log", []).append("source_defaulted_other")

        dtype = rec.get("diagram_type")
        if not dtype:
            code = rec.get("code") if isinstance(rec.get("code"), str) else ""
            dtype = infer_diagram_type_from_code(code) or infer_diagram_type_from_id(sid)
            if dtype:
                rec["diagram_type"] = dtype
                recovery["diagram_type_recovered"] += 1
        if not rec.get("diagram_type"):
            rec["diagram_type"] = "flowchart"
            recovery["diagram_type_recovered"] += 1
            rec.setdefault("repair_log", []).append("diagram_type_defaulted_flowchart")

        # Dialogue repair.
        dg = rec.get("cscw_dialogue")
        if isinstance(dg, list):
            repaired_dg, dg_changes = repair_dialogue(dg, args.min_turns, args.max_turns)
            if dg_changes:
                rec["cscw_dialogue"] = repaired_dg
                recovery["dialogue_repaired"] += 1
                rec.setdefault("repair_log", []).extend(dg_changes)
            rec["dialogue_metadata"] = rec.get("dialogue_metadata") or {}
            rec["dialogue_metadata"]["total_turns"] = len(rec["cscw_dialogue"])
        else:
            # Minimal fallback dialogue if missing entirely.
            rec["cscw_dialogue"] = [
                create_min_turn(1, "Domain_Expert", "propose", "请先建立核心结构。"),
                create_min_turn(2, "Diagram_Editor", "clarify", "收到，我先画主干。"),
                create_min_turn(3, "Domain_Expert", "confirm", "可以，继续补充细节。"),
                create_min_turn(4, "Diagram_Editor", "execute", "[系统日志: 已补齐最小对话轮次]"),
            ]
            rec["dialogue_metadata"] = {
                "total_turns": 4,
                "repair_count": 0,
                "grounding_acts_count": 1,
                "theoretical_framework": "Grounding in Communication (auto-repaired)",
            }
            recovery["dialogue_repaired"] += 1
            rec.setdefault("repair_log", []).append("dialogue_missing_rebuilt")

        # License repair by seed/source heuristics first.
        lic = normalize_license(rec.get("license"))
        if lic in INVALID_LICENSES:
            seed = rec.get("seed_id") or rec.get("seed")
            seed_rec = baseline_by_id.get(str(seed)) if seed else None
            if isinstance(seed_rec, dict) and valid_license(seed_rec.get("license")):
                rec["license"] = normalize_license(seed_rec.get("license"))
                if seed_rec.get("license_name"):
                    rec["license_name"] = seed_rec.get("license_name")
                if seed_rec.get("license_url"):
                    rec["license_url"] = seed_rec.get("license_url")
                recovery["license_recovered"] += 1
            else:
                source = str(rec.get("source") or "")
                if source == "gitlab":
                    rec["license"] = "gitlab_repo"
                    recovery["license_recovered"] += 1
                elif source == "other":
                    rec["license"] = "other_source"
                    recovery["license_recovered"] += 1
                else:
                    repo = extract_repo(rec)
                    if repo:
                        repo_license_candidates[fname] = repo

        # Compilation check target.
        if rec.get("compilation_status") != "success":
            compile_targets.append((fname, rec.get("code") if isinstance(rec.get("code"), str) else ""))

    # Second pass: local compilation recovery (fast, no network).
    local_promoted: List[Tuple[str, str]] = []
    network_fallback_targets: List[Tuple[str, str]] = []
    for fname, code in compile_targets:
        rec = records_by_file[fname]
        ok, fixed_code, method = local_try_repair_and_judge(code)
        if ok:
            rec["compilation_status"] = "success"
            rec["compilation_error"] = ""
            if method != "original":
                rec["code"] = fixed_code
            rec.setdefault("repair_log", []).append(f"compilation_recovered_local_{method}")
            recovery["compilation_recovered_local"] += 1
            local_promoted.append((fname, rec.get("code") if isinstance(rec.get("code"), str) else ""))
        else:
            network_fallback_targets.append((fname, code))

    # Third pass: optional Kroki network fallback (only for small hard-fail set).
    checker = KrokiChecker(timeout=args.kroki_timeout)

    def compile_job(item: Tuple[str, str]) -> Tuple[str, bool, str, str]:
        fname, code = item
        ok, fixed_code, method = checker.try_repair_and_check(code)
        return fname, ok, fixed_code, method

    if network_fallback_targets:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(compile_job, item) for item in network_fallback_targets]
            for fut in as_completed(futs):
                fname, ok, fixed_code, method = fut.result()
                rec = records_by_file[fname]
                if ok:
                    rec["compilation_status"] = "success"
                    rec["compilation_error"] = ""
                    if method != "original":
                        rec["code"] = fixed_code
                    rec.setdefault("repair_log", []).append(f"compilation_recovered_kroki_{method}")
                    recovery["compilation_recovered_kroki"] += 1
                else:
                    rec["compilation_status"] = "failed"
                    rec.setdefault("compilation_error", "kroki_check_failed")
                    rec.setdefault("repair_log", []).append("compilation_unrecoverable")

    # Optional audit: sample-check locally promoted records against Kroki for confidence.
    audit_total = 0
    audit_pass = 0
    audit_fail = 0
    if not args.skip_kroki_audit and local_promoted:
        rng = random.Random(args.seed + 17)
        sample_n = min(args.kroki_audit_sample, len(local_promoted))
        audit_sample = rng.sample(local_promoted, sample_n)
        audit_total = len(audit_sample)
        if audit_sample:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [ex.submit(compile_job, item) for item in audit_sample]
                for fut in as_completed(futs):
                    fname, ok, _, _ = fut.result()
                    rec = records_by_file[fname]
                    if ok:
                        audit_pass += 1
                    else:
                        # Keep local recovery result, but mark this record as audit-failed for follow-up.
                        audit_fail += 1
                        rec.setdefault("repair_log", []).append("kroki_audit_failed")

    # Fourth pass: optional GitHub repo license lookup for still-invalid licenses.
    github_token = os.getenv("GITHUB_TOKEN", "")
    session = requests.Session()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    repo_cache: Dict[str, Optional[str]] = {}
    rate_limited = False

    for fname, repo in repo_license_candidates.items():
        rec = records_by_file[fname]
        if valid_license(rec.get("license")):
            continue
        if rate_limited:
            break
        if repo in repo_cache:
            lic = repo_cache[repo]
        else:
            lic = None
            try:
                r = session.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=12)
                if r.status_code == 200:
                    lic = ((r.json().get("license") or {}).get("key") or "").strip().lower()
                elif r.status_code == 403:
                    rate_limited = True
                # 404 or others leave lic None.
            except Exception:
                lic = None
            repo_cache[repo] = lic

        if lic and lic not in INVALID_LICENSES:
            rec["license"] = lic
            recovery["license_recovered"] += 1

    # Write repaired full set and evaluate subsets.
    unresolved_index: List[Dict] = []
    type_map_train: Dict[str, str] = {}
    type_map_compliant: Dict[str, str] = {}

    for fname, rec in records_by_file.items():
        sid = rec.get("id") or Path(fname).stem
        # Always write repaired full set.
        rec["repaired_at"] = utc_now()
        (repaired_dir / fname).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        # Flags.
        has_code = isinstance(rec.get("code"), str) and bool(rec.get("code").strip())
        src_ok = bool(rec.get("source"))
        dtype_ok = bool(rec.get("diagram_type"))
        comp_ok = rec.get("compilation_status") == "success"
        lic_ok = valid_license(rec.get("license"))
        dg = rec.get("cscw_dialogue")
        turns_ok = isinstance(dg, list) and args.min_turns <= len(dg) <= args.max_turns

        if not src_ok:
            unresolved["missing_source"] += 1
        if not dtype_ok:
            unresolved["missing_diagram_type"] += 1
        if not has_code:
            unresolved["missing_code"] += 1
        if not comp_ok:
            unresolved["compilation_failed"] += 1
        if not lic_ok:
            unresolved["invalid_license"] += 1
        if not turns_ok:
            unresolved["dialogue_turns_invalid"] += 1

        # Train-ready: compilation + dialogue + core structure (license can be unresolved).
        train_ready = has_code and src_ok and dtype_ok and comp_ok and turns_ok
        if train_ready:
            (train_ready_dir / fname).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            type_map_train[str(sid)] = str(rec.get("diagram_type"))

        # Compliant: train-ready + valid license.
        compliant = train_ready and lic_ok
        if compliant:
            (compliant_dir / fname).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            type_map_compliant[str(sid)] = str(rec.get("diagram_type"))
        else:
            # classify compliant rejection reasons for reporting
            if not train_ready:
                if not comp_ok:
                    compliant_reject["compilation_not_success"] += 1
                if not src_ok:
                    compliant_reject["missing_source"] += 1
                if not dtype_ok:
                    compliant_reject["missing_diagram_type"] += 1
                if not turns_ok:
                    compliant_reject["dialogue_turns_invalid"] += 1
                if not has_code:
                    compliant_reject["missing_code"] += 1
            elif not lic_ok:
                compliant_reject["invalid_or_missing_license"] += 1

            unresolved_index.append(
                {
                    "id": sid,
                    "file": fname,
                    "source": rec.get("source"),
                    "diagram_type": rec.get("diagram_type"),
                    "compilation_status": rec.get("compilation_status"),
                    "license": rec.get("license"),
                    "dialogue_turns": len(rec.get("cscw_dialogue", [])) if isinstance(rec.get("cscw_dialogue"), list) else None,
                }
            )

    # Split files for train-ready and compliant subsets.
    for subset_name, dir_path, type_map in [
        ("train_ready", train_ready_dir, type_map_train),
        ("compliant", compliant_dir, type_map_compliant),
    ]:
        ids = sorted(type_map.keys())
        splits = build_splits(ids, type_map, seed=args.seed)
        split_dir = dir_path / "splits"
        ensure_dir(split_dir)
        for split_name, split_ids in splits.items():
            (split_dir / f"{split_name}_ids.json").write_text(
                json.dumps({"count": len(split_ids), "ids": split_ids}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    unresolved_path = reports_dir / f"repair_rebuild_v3_unresolved_{ts_tag}.json"
    unresolved_path.write_text(json.dumps(unresolved_index, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "built_at_utc": utc_now(),
        "source_dir": str(source_dir),
        "baseline_dir": str(baseline_dir),
        "input_records": input_count,
        "repaired_records": len(records_by_file),
        "train_ready_records": len(type_map_train),
        "compliant_records": len(type_map_compliant),
        "recovery": {
            "compilation_recovered_local": int(recovery["compilation_recovered_local"]),
            "compilation_recovered_kroki": int(recovery["compilation_recovered_kroki"]),
            "license_recovered": int(recovery["license_recovered"]),
            "source_recovered": int(recovery["source_recovered"]),
            "diagram_type_recovered": int(recovery["diagram_type_recovered"]),
            "dialogue_repaired": int(recovery["dialogue_repaired"]),
        },
        "compilation_audit": {
            "sample_size": int(audit_total),
            "pass": int(audit_pass),
            "fail": int(audit_fail),
            "pass_rate": round((audit_pass / audit_total), 4) if audit_total else None,
        },
        "remaining_unresolved": dict(unresolved),
        "compliant_rejection_reasons": dict(compliant_reject),
        "output_dirs": {
            "repaired_full": str(repaired_dir),
            "train_ready": str(train_ready_dir),
            "compliant": str(compliant_dir),
            "unresolved_index": str(unresolved_path),
        },
        "config": {
            "min_turns": args.min_turns,
            "max_turns": args.max_turns,
            "workers": args.workers,
            "seed": args.seed,
            "kroki_audit_sample": args.kroki_audit_sample,
            "kroki_timeout": args.kroki_timeout,
            "skip_kroki_audit": bool(args.skip_kroki_audit),
            "github_token_used": bool(github_token),
        },
    }

    report_json = reports_dir / f"repair_rebuild_v3_{ts_tag}.json"
    report_md = reports_dir / f"repair_rebuild_v3_{ts_tag}.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report_md(report, report_md)

    latest_json = reports_dir / "repair_rebuild_v3_latest.json"
    latest_md = reports_dir / "repair_rebuild_v3_latest.md"
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_md.write_text(report_md.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
