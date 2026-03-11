from __future__ import annotations

from collections import Counter
from typing import Iterable

from tools.dialogue_regen.dataset import extract_code_terms
from tools.eval.common import normalize_whitespace


ALLOWED_ROLES = {"Domain_Expert", "Diagram_Editor"}
ALLOWED_ACTIONS = {"propose", "clarify", "confirm", "repair", "execute"}
CORE_ACTIONS = {"propose", "clarify", "confirm", "execute"}


def _multiset_f1(reference: Iterable[str], prediction: Iterable[str]) -> float:
    ref_counts = Counter(str(item) for item in reference if item)
    pred_counts = Counter(str(item) for item in prediction if item)
    if not ref_counts and not pred_counts:
        return 1.0
    if not ref_counts or not pred_counts:
        return 0.0
    overlap = sum(min(ref_counts[item], pred_counts[item]) for item in ref_counts.keys() | pred_counts.keys())
    precision = overlap / max(sum(pred_counts.values()), 1)
    recall = overlap / max(sum(ref_counts.values()), 1)
    denom = precision + recall
    return 0.0 if denom == 0 else round(2 * precision * recall / denom, 4)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _normalize_text(value: str) -> str:
    return normalize_whitespace((value or "").replace("_", " ").replace("-", " ").lower())


def _turn_count_match_score(reference_turns: int, predicted_turns: int) -> float:
    if reference_turns <= 0 and predicted_turns <= 0:
        return 1.0
    if reference_turns <= 0:
        return 0.0
    delta = abs(predicted_turns - reference_turns) / max(reference_turns, 1)
    return round(max(0.0, 1.0 - min(delta, 1.0)), 4)


def score_dialogue(
    *,
    reference_dialogue: list[dict],
    predicted_dialogue: list[dict],
    code: str,
) -> dict:
    predicted_turns = len(predicted_dialogue)
    reference_turns = len(reference_dialogue)
    utterances = [normalize_whitespace(str(turn.get("utterance", ""))) for turn in predicted_dialogue]
    nonempty_utterances = [item for item in utterances if item]

    roles = [str(turn.get("role", "")) for turn in predicted_dialogue]
    actions = [str(turn.get("action_type", "")) for turn in predicted_dialogue]
    reference_roles = [str(turn.get("role", "")) for turn in reference_dialogue]
    reference_actions = [str(turn.get("action_type", "")) for turn in reference_dialogue]

    alternations = 0
    comparisons = 0
    for previous, current in zip(roles, roles[1:]):
        comparisons += 1
        if previous and current and previous != current:
            alternations += 1

    grounded_terms = extract_code_terms(code)
    utterance_blob = "\n".join(_normalize_text(item) for item in utterances if item)
    grounded_hits = 0
    for term in grounded_terms:
        if term and term in utterance_blob:
            grounded_hits += 1

    structured_elements: list[str] = []
    for turn in predicted_dialogue:
        value = turn.get("elements_involved", [])
        if isinstance(value, list):
            structured_elements.extend(_normalize_text(str(item)) for item in value if _normalize_text(str(item)))

    structured_grounded = 0
    grounded_term_set = set(grounded_terms)
    for item in structured_elements:
        if item in grounded_term_set:
            structured_grounded += 1

    role_coverage = len({role for role in roles if role in ALLOWED_ROLES})
    core_action_coverage = len({action for action in actions if action in CORE_ACTIONS})
    avg_utterance_chars = _safe_ratio(sum(len(item) for item in nonempty_utterances), len(nonempty_utterances))
    execute_turns = sum(1 for action in actions if action == "execute")
    repair_turns = sum(1 for action in actions if action == "repair")

    valid_role_rate = _safe_ratio(sum(1 for role in roles if role in ALLOWED_ROLES), predicted_turns)
    valid_action_rate = _safe_ratio(sum(1 for action in actions if action in ALLOWED_ACTIONS), predicted_turns)
    nonempty_utterance_rate = _safe_ratio(len(nonempty_utterances), predicted_turns)
    alternation_rate = _safe_ratio(alternations, comparisons) if comparisons > 0 else 1.0
    grounding_recall = _safe_ratio(grounded_hits, len(grounded_terms))
    structured_element_precision = _safe_ratio(structured_grounded, len(structured_elements))
    turn_count_match_score = _turn_count_match_score(reference_turns, predicted_turns)
    role_f1_vs_reference = _multiset_f1(reference_roles, roles)
    action_f1_vs_reference = _multiset_f1(reference_actions, actions)

    proxy_quality_score = round(
        (
            0.12 * nonempty_utterance_rate
            + 0.10 * valid_role_rate
            + 0.10 * valid_action_rate
            + 0.10 * alternation_rate
            + 0.10 * _safe_ratio(role_coverage, 2)
            + 0.10 * _safe_ratio(core_action_coverage, len(CORE_ACTIONS))
            + 0.18 * grounding_recall
            + 0.08 * structured_element_precision
            + 0.07 * turn_count_match_score
            + 0.05 * action_f1_vs_reference
        ),
        4,
    )

    return {
        "generated_turns": predicted_turns,
        "reference_turns": reference_turns,
        "turn_count_match_score": turn_count_match_score,
        "nonempty_utterance_rate": nonempty_utterance_rate,
        "avg_utterance_chars": avg_utterance_chars,
        "valid_role_rate": valid_role_rate,
        "valid_action_rate": valid_action_rate,
        "alternation_rate": round(alternation_rate, 4),
        "role_coverage_rate": _safe_ratio(role_coverage, 2),
        "core_action_coverage_rate": _safe_ratio(core_action_coverage, len(CORE_ACTIONS)),
        "execute_turn_ratio": _safe_ratio(execute_turns, predicted_turns),
        "repair_turn_ratio": _safe_ratio(repair_turns, predicted_turns),
        "grounding_recall": grounding_recall,
        "structured_element_precision": structured_element_precision,
        "role_f1_vs_reference": role_f1_vs_reference,
        "action_f1_vs_reference": action_f1_vs_reference,
        "proxy_quality_score": proxy_quality_score,
    }
