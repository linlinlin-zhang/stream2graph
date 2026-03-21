#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.eval.common import inject_api_key, load_api_keys_config, resolve_path, write_json
from tools.incremental_system.algorithm import DeterministicAlgorithmLayer
from tools.incremental_system.chat_clients import (
    GeminiGenerateContentChatClient,
    LocalHFChatClient,
    OpenAICompatibleChatClient,
)
from tools.incremental_system.loader import list_completed_sample_ids, load_runtime_sample
from tools.incremental_system.models import LLMGateModel, LLMPlannerModel, OracleGateModel, OraclePlannerModel
from tools.incremental_system.runtime import IncrementalSystemRunner


DEFAULT_RUN_ROOT = "data/incremental_dataset/runs/incremental_open_balanced_v1_3360_public_clean"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the incremental Stream2Graph core system on one sample.")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--run-root", type=str, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--sample-id", type=str, default="")
    parser.add_argument("--output", type=str, default="")
    parser.add_argument(
        "--api-keys-config",
        type=str,
        default="configs/evaluation/model_benchmarks/api_keys.local.json",
    )
    parser.add_argument(
        "--gate-kind",
        type=str,
        default="oracle",
        choices=["oracle", "openai_compatible", "google_generate_content", "local_hf"],
    )
    parser.add_argument(
        "--planner-kind",
        type=str,
        default="oracle",
        choices=["oracle", "openai_compatible", "google_generate_content", "local_hf"],
    )
    parser.add_argument("--gate-endpoint", type=str, default="")
    parser.add_argument("--gate-model", type=str, default="")
    parser.add_argument("--gate-api-key-env", type=str, default="OPENAI_API_KEY")
    parser.add_argument("--gate-api-key", type=str, default="")
    parser.add_argument("--gate-omit-temperature", action="store_true")
    parser.add_argument("--planner-endpoint", type=str, default="")
    parser.add_argument("--planner-model", type=str, default="")
    parser.add_argument("--planner-api-key-env", type=str, default="OPENAI_API_KEY")
    parser.add_argument("--planner-api-key", type=str, default="")
    parser.add_argument("--planner-omit-temperature", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff-sec", type=float, default=3.0)
    parser.add_argument("--request-interval-sec", type=float, default=0.0)
    parser.add_argument("--gate-extra-body-json", type=str, default="")
    parser.add_argument("--planner-extra-body-json", type=str, default="")
    parser.add_argument("--extra-body-json", type=str, default="")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        config_payload = json.loads(resolve_path(pre_args.config).read_text(encoding="utf-8"))
        parser.set_defaults(**config_payload)
    return parser.parse_args()


def _make_client(
    kind: str,
    endpoint: str,
    model: str,
    api_key: str,
    api_key_env: str,
    omit_temperature: bool,
    extra_body_json: str,
    args: argparse.Namespace,
):
    extra_body = json.loads(extra_body_json) if extra_body_json else {}
    client_cls = {
        "openai_compatible": OpenAICompatibleChatClient,
        "google_generate_content": GeminiGenerateContentChatClient,
        "local_hf": LocalHFChatClient,
    }.get(kind)
    if client_cls is None:
        raise ValueError(f"Unsupported incremental chat client kind: {kind}")
    return client_cls(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        timeout_sec=args.timeout_sec,
        max_retries=args.max_retries,
        retry_backoff_sec=args.retry_backoff_sec,
        request_interval_sec=args.request_interval_sec,
        extra_body=extra_body,
        omit_temperature=omit_temperature,
        temperature=args.temperature,
    )


def _build_models(args: argparse.Namespace):
    if args.gate_kind == "oracle":
        gate_model = OracleGateModel()
    else:
        gate_extra_body_json = args.gate_extra_body_json or args.extra_body_json
        gate_client = _make_client(
            kind=args.gate_kind,
            endpoint=args.gate_endpoint,
            model=args.gate_model,
            api_key=args.gate_api_key,
            api_key_env=args.gate_api_key_env,
            omit_temperature=args.gate_omit_temperature,
            extra_body_json=gate_extra_body_json,
            args=args,
        )
        gate_model = LLMGateModel(gate_client)

    if args.planner_kind == "oracle":
        planner_model = OraclePlannerModel()
    else:
        planner_extra_body_json = args.planner_extra_body_json or args.extra_body_json
        planner_client = _make_client(
            kind=args.planner_kind,
            endpoint=args.planner_endpoint,
            model=args.planner_model,
            api_key=args.planner_api_key,
            api_key_env=args.planner_api_key_env,
            omit_temperature=args.planner_omit_temperature,
            extra_body_json=planner_extra_body_json,
            args=args,
        )
        planner_model = LLMPlannerModel(planner_client)
    return gate_model, planner_model


def main() -> None:
    args = parse_args()
    api_keys = load_api_keys_config(args.api_keys_config)
    inject_api_key(args.gate_api_key_env, args.gate_api_key or api_keys.get(args.gate_api_key_env, ""))
    inject_api_key(args.planner_api_key_env, args.planner_api_key or api_keys.get(args.planner_api_key_env, ""))
    sample_id = args.sample_id
    if not sample_id:
        completed = list_completed_sample_ids(args.run_root, limit=1)
        if not completed:
            raise SystemExit("No completed samples found under the run root.")
        sample_id = completed[0]

    sample = load_runtime_sample(args.run_root, sample_id)
    gate_model, planner_model = _build_models(args)
    runner = IncrementalSystemRunner(
        algorithm_layer=DeterministicAlgorithmLayer(),
        gate_model=gate_model,
        planner_model=planner_model,
    )
    payload = runner.run_sample(sample)

    if args.output:
        write_json(resolve_path(args.output), payload)
        print(f"Output: {resolve_path(args.output)}")
    else:
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
