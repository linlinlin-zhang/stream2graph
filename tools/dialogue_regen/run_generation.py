#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.dialogue_regen.dataset import (
    DEFAULT_SOURCE_DIR,
    DEFAULT_SPLIT_DIR,
    load_regen_samples,
)
from tools.dialogue_regen.parsing import parse_generated_dialogue
from tools.dialogue_regen.providers import build_generator
from tools.eval.common import append_jsonl, read_jsonl, resolve_path, utc_iso, write_json


def _load_sample_ids(path_value: str) -> set[str]:
    if not path_value:
        return set()
    path = resolve_path(path_value)
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            values = payload.get("ids", [])
        else:
            values = payload
        return {str(item) for item in values}
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified LLM dialogue regeneration runner.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--source-dir", type=str, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--split-dir", type=str, default=DEFAULT_SPLIT_DIR)
    parser.add_argument("--split", type=str, default="validation", choices=["train", "validation", "test", "all"])
    parser.add_argument("--output-jsonl", type=str, default="reports/dialogue_regen/runs/generation.jsonl")
    parser.add_argument("--manifest-output", type=str, default="")
    parser.add_argument("--target-language", type=str, default="zh-CN")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--sample-ids-file", type=str, default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--provider", type=str, default="reference_dialogue")
    parser.add_argument("--provider-name", type=str, default="")
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--endpoint", type=str, default="")
    parser.add_argument("--api-key-env", type=str, default="")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff-sec", type=float, default=3.0)
    parser.add_argument("--request-interval-sec", type=float, default=0.0)
    parser.add_argument("--thinking-budget", type=int, default=0)

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_jsonl = resolve_path(args.output_jsonl)
    manifest_output = (
        resolve_path(args.manifest_output)
        if args.manifest_output
        else output_jsonl.with_suffix(".manifest.json")
    )

    selected_ids = _load_sample_ids(args.sample_ids_file)
    samples = load_regen_samples(
        source_dir=args.source_dir,
        split_dir=args.split_dir,
        split=args.split,
        max_samples=args.max_samples,
        sample_ids=selected_ids if selected_ids else None,
        target_language=args.target_language,
    )

    completed_ids: set[str] = set()
    if args.resume and output_jsonl.exists():
        completed_ids = {str(row.get("sample_id")) for row in read_jsonl(output_jsonl)}
    elif output_jsonl.exists():
        output_jsonl.unlink()

    generator_config = {
        "provider": args.provider,
        "provider_name": args.provider_name or args.provider,
        "model": args.model,
        "endpoint": args.endpoint,
        "api_key_env": args.api_key_env,
        "temperature": args.temperature,
        "max_output_tokens": args.max_output_tokens,
        "max_tokens": args.max_tokens,
        "timeout_sec": args.timeout_sec,
        "max_retries": args.max_retries,
        "retry_backoff_sec": args.retry_backoff_sec,
        "request_interval_sec": args.request_interval_sec,
        "thinking_budget": args.thinking_budget,
    }
    raw_config = json.loads(resolve_path(args.config).read_text(encoding="utf-8")) if args.config else {}
    if isinstance(raw_config.get("extra_body"), dict):
        generator_config["extra_body"] = raw_config["extra_body"]

    generator = build_generator(generator_config)
    processed = 0
    failures = 0
    skipped = 0
    parse_failures = 0

    for sample in samples:
        if sample.sample_id in completed_ids:
            skipped += 1
            continue

        result = generator.generate(sample)
        parsed_dialogue = None
        parse_error = None
        parse_warnings: list[str] = []
        if not result.error:
            parsed_dialogue, parse_error = parse_generated_dialogue(
                result.raw_output_text,
                sample_id=sample.sample_id,
                requested_language=args.target_language,
            )
            if parsed_dialogue is not None:
                parse_warnings = parsed_dialogue.get("parse_warnings", [])
        if result.error or parse_error:
            failures += 1
        if parse_error:
            parse_failures += 1

        row = {
            "generated_at_utc": utc_iso(),
            "sample_id": sample.sample_id,
            "split": sample.split,
            "diagram_type": sample.diagram_type,
            "source_path": sample.source_path,
            "source_url": sample.source_url,
            "reference_dialogue_turns": sample.reference_dialogue_turns,
            "provider": result.provider,
            "model_name": result.model_name,
            "prompt": sample.prompt,
            "raw_output_text": result.raw_output_text,
            "generated_dialogue": parsed_dialogue,
            "target_language": args.target_language,
            "latency_ms": result.latency_ms,
            "finish_reason": result.finish_reason,
            "usage": result.usage,
            "parse_valid": bool(parsed_dialogue and not parse_error),
            "parse_warnings": parse_warnings,
            "error": result.error or parse_error,
        }
        append_jsonl(output_jsonl, row)
        processed += 1
        print(
            f"[dialogue-regen] sample={sample.sample_id} split={sample.split} "
            f"provider={result.provider} model={result.model_name} "
            f"latency_ms={result.latency_ms:.2f} parse_valid={row['parse_valid']} "
            f"error={bool(row['error'])}",
            flush=True,
        )

    generator.close()

    manifest = {
        "generated_at_utc": utc_iso(),
        "source_dir": str(resolve_path(args.source_dir)),
        "split_dir": str(resolve_path(args.split_dir)),
        "split": args.split,
        "sample_count_requested": len(samples),
        "sample_count_processed": processed,
        "sample_count_skipped": skipped,
        "failure_count": failures,
        "parse_failure_count": parse_failures,
        "output_jsonl": str(output_jsonl),
        "generator": generator_config,
    }
    write_json(manifest_output, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

