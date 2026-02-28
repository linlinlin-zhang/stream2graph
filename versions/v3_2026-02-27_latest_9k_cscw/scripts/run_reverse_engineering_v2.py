#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run CSCW dialogue reverse engineering (V2).

升级点:
1. 使用 cscw_dialogue_engine_v2 的结构化元数据输出
2. 支持 overwrite / limit / resume
3. 生成简要运行报告，便于后续实验统计
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Dict

from cscw_dialogue_engine import Turn, run_cscw_engine_with_metadata


def turn_to_dict(turn: Turn) -> Dict:
    return {
        "turn_id": turn.turn_id,
        "role": turn.role,
        "action_type": turn.action_type,
        "utterance": turn.utterance,
        "elements_involved": turn.elements_involved,
        "is_repair": turn.is_repair,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CSCW reverse engineering pipeline V2.")
    parser.add_argument(
        "--input-dir",
        default="/home/lin-server/pictures/stream2graph_dataset/final_v2_9k",
        help="Input JSON directory",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset",
        help="Output JSON directory",
    )
    parser.add_argument(
        "--report-file",
        default="/home/lin-server/pictures/stream2graph_dataset/cscw_dialogue_dataset/_generation_report_v2.json",
        help="Run report output file",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N files (0 means all)")
    return parser.parse_args()


def run_cscw_reverse_engineering() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    report_file = Path(args.report_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.json"))
    if args.limit > 0:
        files = files[: args.limit]
    total_files = len(files)
    print(f"--- 启动 CSCW 级逆向工程对话生成 V2 (总数: {total_files}) ---")

    processed = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    intent_counter: Counter = Counter()
    warn_counter: Counter = Counter()

    for f in files:
        output_file = output_dir / f.name
        if output_file.exists() and not args.overwrite:
            skipped += 1
            continue

        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)

            code = data.get("code", "")
            if not isinstance(code, str) or not code.strip():
                failed += 1
                continue

            dialogue_turns, metadata = run_cscw_engine_with_metadata(code)
            data["cscw_dialogue"] = [turn_to_dict(t) for t in dialogue_turns]
            data["dialogue_metadata"] = metadata
            data["dialogue_metadata"]["generator_runtime_version"] = "run_reverse_engineering_v2"
            data["dialogue_metadata"]["generated_at_epoch"] = int(time.time())

            with open(output_file, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, indent=2)

            processed += 1
            intent_counter[metadata.get("intent_type", "unknown")] += 1
            for w in metadata.get("parser_warnings", []):
                warn_counter[w] += 1

            if (processed + skipped) % 500 == 0:
                elapsed = time.time() - start_time
                print(
                    f"  进度: {processed + skipped}/{total_files} "
                    f"(processed={processed}, skipped={skipped}, failed={failed}, 耗时={elapsed:.2f}s)"
                )

        except Exception:
            failed += 1
            continue

    elapsed = time.time() - start_time
    report = {
        "pipeline": "cscw_reverse_engineering_v2",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_files": total_files,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "elapsed_seconds": round(elapsed, 3),
        "intent_distribution": dict(intent_counter),
        "top_parser_warnings": warn_counter.most_common(10),
    }
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- CSCW 级逆向工程生成完毕 (V2) ---")
    print(f"成功处理: {processed}, 跳过: {skipped}, 失败: {failed}")
    print(f"输出目录: {output_dir}")
    print(f"运行报告: {report_file}")


if __name__ == "__main__":
    run_cscw_reverse_engineering()
