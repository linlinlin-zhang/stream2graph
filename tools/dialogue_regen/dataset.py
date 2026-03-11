from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.eval.common import normalize_whitespace, resolve_path
from tools.eval.dataset import load_split_ids
from tools.eval.metrics import extract_graph_features, normalize_mermaid


SYSTEM_PROMPT = (
    "You generate realistic collaborative CSCW dialogue from Mermaid code. "
    "Return exactly one JSON object and nothing else. "
    "The JSON must have keys: sample_id, dialogue_language, cscw_dialogue. "
    "Each turn in cscw_dialogue must have: turn_id, role, action_type, utterance, "
    "elements_involved, is_repair. "
    "Allowed roles: Domain_Expert, Diagram_Editor. "
    "Allowed action_type values: propose, clarify, confirm, repair, execute. "
    "Keep the dialogue grounded in the Mermaid structure, but make it sound like a real "
    "collaborative diagram-building conversation instead of a line-by-line code recital."
)

DEFAULT_SOURCE_DIR = (
    "versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v4_20260311"
)
DEFAULT_SPLIT_DIR = (
    "versions/v3_2026-02-27_latest_9k_cscw/dataset/stream2graph_dataset/release_v4_20260311/splits"
)


@dataclass
class DialogueRegenSample:
    sample_id: str
    split: str
    diagram_type: str
    code: str
    prompt: str
    source_path: str
    source_url: str
    reference_dialogue_turns: int
    metadata: dict
    raw_sample: dict


def _normalize_term(value: str) -> str:
    lowered = value.replace("_", " ").replace("-", " ").strip().lower()
    return normalize_whitespace(lowered)


def extract_code_terms(code: str, limit: int = 24) -> list[str]:
    features = extract_graph_features(code)
    ordered: list[str] = []
    seen: set[str] = set()

    for label in features["labels"]:
        term = _normalize_term(label)
        if len(term) < 3 or term in seen:
            continue
        seen.add(term)
        ordered.append(term)

    for node in features["nodes"]:
        term = _normalize_term(node)
        if len(term) < 3 and "_" not in node and not any(ch.isdigit() for ch in node):
            continue
        if term in seen:
            continue
        seen.add(term)
        ordered.append(term)

    return ordered[:limit]


def build_user_prompt(
    sample: dict,
    *,
    target_language: str = "zh-CN",
    target_turn_floor: int = 8,
    target_turn_cap: int = 64,
) -> str:
    reference_turns = len(sample.get("cscw_dialogue", []))
    target_turns = max(target_turn_floor, min(target_turn_cap, reference_turns or 12))
    min_turns = max(6, target_turns - 4)
    max_turns = min(target_turn_cap, target_turns + 6)
    code_terms = extract_code_terms(str(sample.get("code", "")))
    code_block = normalize_mermaid(str(sample.get("code", "")))

    lines = [
        "Generate a collaborative dialogue that could plausibly lead to the final Mermaid diagram below.",
        "The dialogue should feel like a real working session between a domain expert and a diagram editor.",
        "Use the final repaired state implied by the code, but do not expose the code directly in the dialogue.",
        "Language requirement:",
        f"- Produce the utterances in {target_language}.",
        "Conversation requirements:",
        f"- Aim for about {target_turns} turns. Acceptable range: {min_turns}-{max_turns}.",
        "- Alternate naturally between Domain_Expert and Diagram_Editor.",
        "- Use propose, clarify, confirm, and execute turns regularly. Use repair only when needed.",
        "- Mention concrete diagram elements and relationships grounded in the Mermaid code.",
        "- Avoid generic filler and avoid reading the code line by line.",
        "Output requirements:",
        "- Return exactly one JSON object.",
        '- Set dialogue_language to the requested language value, for example "zh-CN".',
        "- Do not include markdown fences, explanations, or comments outside the JSON.",
        "",
        f"Sample ID: {sample['id']}",
        f"Diagram type: {sample.get('diagram_type', 'unknown')}",
        f"Suggested grounded terms: {', '.join(code_terms) if code_terms else 'none'}",
        "",
        "Mermaid code:",
        "```mermaid",
        code_block,
        "```",
        "",
        "Required JSON shape:",
        "{",
        '  "sample_id": "..." ,',
        '  "dialogue_language": "zh-CN",',
        '  "cscw_dialogue": [',
        "    {",
        '      "turn_id": 1,',
        '      "role": "Domain_Expert",',
        '      "action_type": "propose",',
        '      "utterance": "...",',
        '      "elements_involved": ["..."],',
        '      "is_repair": false',
        "    }",
        "  ]",
        "}",
    ]
    return "\n".join(lines).strip()


def build_messages(sample: DialogueRegenSample) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sample.prompt},
    ]


def load_regen_samples(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    split_dir: str | Path = DEFAULT_SPLIT_DIR,
    split: str = "validation",
    max_samples: int = 0,
    sample_ids: Optional[set[str]] = None,
    target_language: str = "zh-CN",
) -> list[DialogueRegenSample]:
    source_dir = resolve_path(source_dir)
    split_dir = resolve_path(split_dir)
    split_map = load_split_ids(split_dir)

    if split == "all":
        ordered_ids: list[tuple[str, str]] = []
        for split_name in ("train", "validation", "test"):
            ordered_ids.extend((sample_id, split_name) for sample_id in split_map[split_name])
    else:
        ordered_ids = [(sample_id, split) for sample_id in split_map[split]]

    rows: list[DialogueRegenSample] = []
    for sample_id, sample_split in ordered_ids:
        if sample_ids is not None and sample_id not in sample_ids:
            continue
        sample_path = source_dir / f"{sample_id}.json"
        if not sample_path.exists():
            continue
        raw = json.loads(sample_path.read_text(encoding="utf-8"))
        rows.append(
            DialogueRegenSample(
                sample_id=sample_id,
                split=sample_split,
                diagram_type=str(raw.get("diagram_type", "unknown")),
                code=str(raw.get("code", "")).rstrip() + "\n",
                prompt=build_user_prompt(raw, target_language=target_language),
                source_path=str(sample_path),
                source_url=str(raw.get("source_url", "")),
                reference_dialogue_turns=len(raw.get("cscw_dialogue", [])),
                metadata={
                    "source": raw.get("source"),
                    "license": raw.get("license"),
                    "compilation_status": raw.get("compilation_status"),
                },
                raw_sample=raw,
            )
        )
        if max_samples > 0 and len(rows) >= max_samples:
            break
    return rows

