from __future__ import annotations

from collections import defaultdict

from tools.eval.common import sha256_text


def _allocate_evenly(available_counts: dict[str, int], target: int) -> dict[str, int]:
    quotas = {key: 0 for key in available_counts}
    keys = sorted(available_counts)
    if target <= 0 or not keys:
        return quotas
    remaining = target
    while remaining > 0:
        progressed = False
        for key in keys:
            if quotas[key] >= available_counts[key]:
                continue
            quotas[key] += 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            break
    return quotas


def _sort_for_selection(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda item: (
            not bool(item.get("compile_success")),
            bool(item.get("augmented")),
            -float(item.get("complexity_score", 0.0)),
            sha256_text(str(item.get("sample_id"))),
        ),
    )


def select_profiles(profiles: list[dict], target_samples: int = 3000) -> dict:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for profile in profiles:
        by_type[str(profile["diagram_type"])].append(profile)

    type_quotas = _allocate_evenly({key: len(value) for key, value in by_type.items()}, target_samples)
    selected: list[dict] = []
    selection_stats: dict[str, dict] = {}

    for diagram_type in sorted(by_type):
        type_rows = by_type[diagram_type]
        bucket_rows: dict[int, list[dict]] = defaultdict(list)
        for row in type_rows:
            bucket_rows[int(row.get("complexity_bucket", 1))].append(row)
        bucket_quotas = _allocate_evenly(
            {str(bucket): len(rows) for bucket, rows in bucket_rows.items()},
            type_quotas[diagram_type],
        )

        chosen_for_type: list[dict] = []
        for bucket in sorted(bucket_rows):
            rows = _sort_for_selection(bucket_rows[bucket])
            take = bucket_quotas.get(str(bucket), 0)
            chosen_for_type.extend(rows[:take])

        if len(chosen_for_type) < type_quotas[diagram_type]:
            chosen_ids = {row["sample_id"] for row in chosen_for_type}
            leftovers = [row for row in _sort_for_selection(type_rows) if row["sample_id"] not in chosen_ids]
            chosen_for_type.extend(leftovers[: type_quotas[diagram_type] - len(chosen_for_type)])

        selected.extend(chosen_for_type)
        selection_stats[diagram_type] = {
            "available": len(type_rows),
            "selected": len(chosen_for_type),
            "quota": type_quotas[diagram_type],
        }

    selected = _sort_for_selection(selected)[:target_samples]
    split_stats = assign_splits(selected)

    return {
        "target_samples": target_samples,
        "selected_count": len(selected),
        "selection_stats": selection_stats,
        "selected_profiles": selected,
        "split_stats": split_stats,
    }


def assign_splits(selected_profiles: list[dict], train_ratio: float = 0.8, validation_ratio: float = 0.1) -> dict[str, int]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in selected_profiles:
        key = f"{row['diagram_type']}::{row.get('complexity_bucket', 1)}"
        grouped[key].append(row)

    counters = {"train": 0, "validation": 0, "test": 0}
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda item: sha256_text(str(item["sample_id"])))
        total = len(rows)
        train_cut = int(round(total * train_ratio))
        validation_cut = train_cut + int(round(total * validation_ratio))
        for index, row in enumerate(rows):
            if index < train_cut:
                split = "train"
            elif index < validation_cut:
                split = "validation"
            else:
                split = "test"
            row["incremental_split"] = split
            counters[split] += 1
    return counters
