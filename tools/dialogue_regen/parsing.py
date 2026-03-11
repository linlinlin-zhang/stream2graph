from __future__ import annotations

import json
import re
from typing import Any

from tools.eval.common import normalize_whitespace, strip_code_fences, strip_think_traces


ROLE_MAP = {
    "domain_expert": "Domain_Expert",
    "expert": "Domain_Expert",
    "domain expert": "Domain_Expert",
    "diagram_editor": "Diagram_Editor",
    "editor": "Diagram_Editor",
    "diagram editor": "Diagram_Editor",
}

ACTION_MAP = {
    "propose": "propose",
    "clarify": "clarify",
    "confirm": "confirm",
    "repair": "repair",
    "execute": "execute",
}


def _extract_json_block(text: str) -> str:
    raw = strip_think_traces(text or "")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    raw = strip_code_fences(raw)

    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = raw.find(start_char)
        end = raw.rfind(end_char)
        if start >= 0 and end > start:
            candidate = raw[start : end + 1].strip()
            if candidate:
                return candidate
    return raw.strip()


def _canonical_role(value: Any, index: int) -> str:
    key = normalize_whitespace(str(value or "")).replace("-", " ").replace("_", " ").lower()
    if key in ROLE_MAP:
        return ROLE_MAP[key]
    return "Domain_Expert" if index % 2 == 1 else "Diagram_Editor"


def _canonical_action(value: Any) -> str:
    key = normalize_whitespace(str(value or "")).replace("-", "_").replace(" ", "_").lower()
    return ACTION_MAP.get(key, "propose")


def _normalize_elements(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [normalize_whitespace(str(item)) for item in value if normalize_whitespace(str(item))]
        return items[:16]
    if isinstance(value, str):
        parts = [normalize_whitespace(item) for item in re.split(r"[,\|;/]", value) if normalize_whitespace(item)]
        return parts[:16]
    return []


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def parse_generated_dialogue(
    raw_text: str,
    *,
    sample_id: str,
    requested_language: str = "zh-CN",
) -> tuple[dict[str, Any] | None, str | None]:
    candidate = _extract_json_block(raw_text)
    if not candidate:
        return None, "empty_output"

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"

    if isinstance(payload, list):
        payload = {
            "sample_id": sample_id,
            "dialogue_language": requested_language,
            "cscw_dialogue": payload,
        }
    if not isinstance(payload, dict):
        return None, "json_root_not_object"

    turns = payload.get("cscw_dialogue")
    if not isinstance(turns, list):
        alt_turns = payload.get("dialogue")
        if isinstance(alt_turns, list):
            turns = alt_turns
        else:
            return None, "missing_cscw_dialogue_list"

    normalized_turns: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, raw_turn in enumerate(turns, start=1):
        if not isinstance(raw_turn, dict):
            warnings.append(f"turn_{index}_not_object")
            continue
        utterance = normalize_whitespace(
            str(raw_turn.get("utterance") or raw_turn.get("content") or raw_turn.get("text") or "")
        )
        if not utterance:
            warnings.append(f"turn_{index}_empty_utterance")
            continue
        action = _canonical_action(raw_turn.get("action_type"))
        role = _canonical_role(raw_turn.get("role"), index)
        normalized_turns.append(
            {
                "turn_id": index,
                "role": role,
                "action_type": action,
                "utterance": utterance,
                "elements_involved": _normalize_elements(raw_turn.get("elements_involved")),
                "is_repair": _safe_bool(raw_turn.get("is_repair")) or action == "repair",
            }
        )

    if not normalized_turns:
        return None, "no_valid_turns_after_normalization"

    normalized = {
        "sample_id": str(payload.get("sample_id") or sample_id),
        "dialogue_language": str(payload.get("dialogue_language") or requested_language),
        "cscw_dialogue": normalized_turns,
        "parse_warnings": warnings,
    }
    return normalized, None
