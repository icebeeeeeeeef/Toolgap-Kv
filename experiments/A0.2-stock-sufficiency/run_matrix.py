#!/usr/bin/env python3
"""Run exactly one registered A0.2 comparative matrix ordinal."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.metadata as importlib_metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
RAW_ROOT = EXPERIMENT_DIR / "raw"
CALIBRATION = RAW_ROOT / "calibration/calibration-a01/calibration.json"
PREFLIGHT = RAW_ROOT / "preflight/preflight-a01"
QUALIFICATION_DIR = REPOSITORY_ROOT / "experiments/A0.2-foreground-length-qualification"
QUALIFICATION_RUNNER = QUALIFICATION_DIR / "run_qualification.py"
A01R_RUNNER = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual/run_task0.py"
SPEC = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/A0.2-stock-sufficiency-spec.md"
DESIGN = REPOSITORY_ROOT / "docs/superpowers/specs/2026-07-22-a02-stock-sufficiency-design.md"

if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from a02 import (
    ScheduleItem,
    decide_run,
    evaluate_foreground,
    registered_schedule,
    schedule_sha256,
    token_ids_sha256,
    write_bundle,
)
from payloads import build_payload_plan, payload_plan_sha256
from run_calibration import ACTIVE_PROBE_COUNT, BLOCK_SIZE, PAYLOAD_BLOCK_CAP
from run_preflight import _source_summary, _usable_token_ids, _worker_engine
from runtime import RequestTrace, collect_request, run_requests, sum_connector_records


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinal", type=int, choices=range(1, 91), required=True)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args(argv)
    if args.attempt <= 0:
        parser.error("--attempt must be positive")
    return args


def schedule_item(ordinal: int) -> ScheduleItem:
    if type(ordinal) is not int or not 1 <= ordinal <= 90:
        raise ValueError("ordinal must be in [1, 90]")
    return registered_schedule()[ordinal - 1]


def destination_for(raw_root: Path, item: ScheduleItem, attempt: int) -> Path:
    if attempt <= 0:
        raise ValueError("attempt must be positive")
    return (
        raw_root
        / "matrix"
        / f"L{item.length}"
        / item.band
        / f"pair-{item.pair:02d}"
        / f"ordinal-{item.ordinal:03d}-{item.policy}-a{attempt:02d}"
    )


def request_timing(metrics: Any) -> dict[str, float | None]:
    if metrics is None:
        return {
            "queued_ts": None,
            "scheduled_ts": None,
            "first_token_ts": None,
            "last_token_ts": None,
            "queue_delay_seconds": None,
            "prefill_seconds": None,
            "ttft_seconds": None,
            "service_seconds": None,
        }
    queued = float(metrics.queued_ts)
    scheduled = float(metrics.scheduled_ts)
    first = float(metrics.first_token_ts)
    last = float(metrics.last_token_ts)
    if not (0 < queued <= scheduled <= first <= last):
        raise ValueError("engine monotonic request timestamps are missing or unordered")
    return {
        "queued_ts": queued,
        "scheduled_ts": scheduled,
        "first_token_ts": first,
        "last_token_ts": last,
        "queue_delay_seconds": scheduled - queued,
        "prefill_seconds": first - scheduled,
        "ttft_seconds": first - queued,
        "service_seconds": first - scheduled,
    }


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_gate_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    calibration = _load_json(CALIBRATION)
    preflight = _load_json(PREFLIGHT / "verdict.json")
    if calibration.get("status") != "valid":
        raise RuntimeError("calibration gate is not valid")
    if preflight.get("status") != "valid":
        raise RuntimeError("connector/probe preflight gate is not valid")
    if calibration.get("schedule_sha256") != schedule_sha256(registered_schedule()):
        raise RuntimeError("calibration schedule hash drifted")
    if preflight.get("transfer_overlap_observable") is not False:
        raise RuntimeError("preflight overlap observability contract drifted")
    return calibration, preflight


def _tracked_inputs(item: ScheduleItem) -> tuple[dict[str, str], str]:
    paths = (
        EXPERIMENT_DIR / "a02.py",
        EXPERIMENT_DIR / "payloads.py",
        EXPERIMENT_DIR / "runtime.py",
        EXPERIMENT_DIR / "run_calibration.py",
        EXPERIMENT_DIR / "run_preflight.py",
        EXPERIMENT_DIR / "run_matrix.py",
        SPEC,
        DESIGN,
        A01R_RUNNER,
        QUALIFICATION_RUNNER,
        QUALIFICATION_DIR / "anchors" / f"foreground-{item.length}.json",
        QUALIFICATION_DIR / "fixtures" / f"foreground-{item.length}.json",
    )
    relative = [str(path.relative_to(REPOSITORY_ROOT)) for path in paths]
    for path in relative:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        )
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *relative],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    project_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return ({str(path.relative_to(REPOSITORY_ROOT)): _sha256(path) for path in paths}, project_head)


def _output_ids(output: Any, field: str) -> list[int]:
    value = getattr(output, field, None)
    if not isinstance(value, (list, tuple)) or any(type(token) is not int for token in value):
        raise ValueError(f"RequestOutput.{field} is not an engine-owned integer sequence")
    return list(value)


def _output_record(output: Any, trace: RequestTrace) -> dict[str, Any]:
    completion = output.outputs[0]
    return {
        "request_id": str(output.request_id),
        "prompt_token_ids": _output_ids(output, "prompt_token_ids"),
        "completion_token_ids": _output_ids(completion, "token_ids"),
        "completion_text": str(completion.text),
        "num_cached_tokens": getattr(output, "num_cached_tokens", None),
        "trace": trace.as_dict(),
        "timing": request_timing(getattr(output, "metrics", None)),
    }


def normalize_canonical_messages(
    messages: Sequence[Mapping[str, Any]],
    expected_tool: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Make the qualification path's in-place chat normalization explicit."""
    normalized = deepcopy(list(messages))
    assistants = [
        message
        for message in normalized
        if isinstance(message, Mapping)
        and message.get("role") == "assistant"
        and "tool_calls" in message
    ]
    if len(assistants) != 1:
        raise ValueError("canonical history must contain exactly one assistant tool call")
    calls = assistants[0].get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("canonical history must contain exactly one assistant tool call")
    function = calls[0].get("function") if isinstance(calls[0], Mapping) else None
    if not isinstance(function, dict):
        raise ValueError("canonical assistant tool call has no function mapping")
    if function.get("name") != expected_tool.get("name"):
        raise ValueError("canonical assistant tool name differs from parsed R0")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise ValueError("canonical assistant arguments are not JSON") from error
    if arguments != expected_tool.get("arguments"):
        raise ValueError("canonical assistant arguments differ from parsed R0")
    function["arguments"] = arguments
    return normalized


def _canonical_r1(
    *,
    a01r: Any,
    qualification: Any,
    fixture: Mapping[str, Any],
    tokenizer: Any,
    r0: Mapping[str, Any],
) -> dict[str, Any]:
    from toolgap_kv.a01 import Span, message_region_from_prefixes

    messages, parser, r0_tool, tool_call_id = qualification._canonical_r1_messages(
        a01r, fixture, tokenizer, r0
    )
    messages = normalize_canonical_messages(messages, r0_tool)
    prompt_ids = a01r._render_ids(tokenizer, messages, fixture["tools"])
    rendered = a01r._render_text(tokenizer, messages, fixture["tools"])
    initial_rendered = tokenizer.apply_chat_template(
        list(fixture["initial_messages"]),
        tools=list(fixture["tools"]),
        tokenize=False,
        add_generation_prompt=False,
    )
    through_assistant = tokenizer.apply_chat_template(
        messages[: len(fixture["initial_messages"]) + 1],
        tools=list(fixture["tools"]),
        tokenize=False,
        add_generation_prompt=False,
    )
    assistant_start, assistant_end = message_region_from_prefixes(
        rendered, str(initial_rendered), str(through_assistant)
    )
    open_marker = str(parser.tool_call_start_token)
    close_marker = str(parser.tool_call_end_token)
    r1_span = a01r._span_for_full_render(
        tokenizer,
        rendered,
        prompt_ids,
        open_marker,
        close_marker,
        search_start=assistant_start,
        search_end=assistant_end,
    )
    r0_text = tokenizer.decode(
        r0["completion_token_ids"],
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )
    r0_completion_span = a01r._span_for_full_render(
        tokenizer, r0_text, r0["completion_token_ids"], open_marker, close_marker
    )
    r0_span = Span(
        start=len(r0["prompt_token_ids"]) + r0_completion_span.start,
        end=len(r0["prompt_token_ids"]) + r0_completion_span.end,
        left_boundary_expansion=r0_completion_span.left_boundary_expansion,
        right_boundary_expansion=r0_completion_span.right_boundary_expansion,
    )
    envelope_start = rendered.index(open_marker, assistant_start, assistant_end)
    envelope_end = rendered.index(close_marker, envelope_start, assistant_end) + len(close_marker)
    r1_tool = a01r._parse_one_tool_call(parser, rendered[envelope_start:envelope_end])
    if r0_tool != r1_tool:
        raise ValueError("R0/R1 parser structures differ")
    return {
        "messages": messages,
        "prompt_token_ids": prompt_ids,
        "r0_span": [r0_span.start, r0_span.end],
        "r1_span": [r1_span.start, r1_span.end],
        "r0_tool": r0_tool,
        "r1_tool": r1_tool,
        "tool_call_id": tool_call_id,
    }


def _cell(calibration: Mapping[str, Any], item: ScheduleItem) -> dict[str, Any]:
    return next(
        dict(cell)
        for cell in calibration["cells"]
        if cell["length"] == item.length and cell["band"] == item.band
    )


def _expected_payload_hash(calibration: Mapping[str, Any], item: ScheduleItem) -> str:
    summary = next(
        plan
        for plan in calibration["payload_plans"]
        if plan["length"] == item.length and plan["band"] == item.band and plan["pair"] == item.pair
    )
    return str(summary["payload_plan_sha256"])


async def _execute(
    item: ScheduleItem,
    attempt: int,
    calibration: Mapping[str, Any],
    preflight: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    project_head: str,
) -> dict[str, Any]:
    engine, recorder, a01r, model_snapshot = _worker_engine(item.policy, calibration)
    try:
        qualification = _load_module(QUALIFICATION_RUNNER, f"a02_matrix_qualification_{item.ordinal}")
        fixture_path = QUALIFICATION_DIR / "fixtures" / f"foreground-{item.length}.json"
        anchor_path = QUALIFICATION_DIR / "anchors" / f"foreground-{item.length}.json"
        fixture = _load_json(fixture_path)
        anchor = _load_json(anchor_path)
        tokenizer = engine.get_tokenizer()
        r0_prompt_ids = a01r._render_ids(tokenizer, fixture["initial_messages"], fixture["tools"])
        r0_output, r0_trace = await collect_request(
            engine,
            prompt_token_ids=r0_prompt_ids,
            request_id=f"a02-o{item.ordinal:03d}-r0",
            max_tokens=256,
            ignore_eos=False,
        )
        r0 = _output_record(r0_output, r0_trace)
        r0["r0_ids"] = r0["prompt_token_ids"] + r0["completion_token_ids"]
        canonical = _canonical_r1(
            a01r=a01r,
            qualification=qualification,
            fixture=fixture,
            tokenizer=tokenizer,
            r0=r0,
        )

        cell = _cell(calibration, item)
        plan = build_payload_plan(
            total_blocks=int(cell["builder_target_blocks"]),
            block_size=BLOCK_SIZE,
            nonce=item.nonce,
            usable_token_ids=_usable_token_ids(tokenizer),
            foreground_first_block=canonical["prompt_token_ids"][:BLOCK_SIZE],
            payload_block_cap=PAYLOAD_BLOCK_CAP,
            active_probe_count=ACTIVE_PROBE_COUNT,
        )
        plan_hash = payload_plan_sha256(plan)
        if plan_hash != _expected_payload_hash(calibration, item):
            raise ValueError("payload plan hash differs from calibration")

        builders = [payload for payload in plan if payload.role == "builder"]
        active = [payload for payload in plan if payload.role == "active_probe"]
        builder_results = await run_requests(
            engine,
            [
                (payload.prompt_token_ids, f"a02-o{item.ordinal:03d}-builder-{payload.index}", 1)
                for payload in builders
            ],
        )
        active_traces = [
            RequestTrace(request_id=f"a02-o{item.ordinal:03d}-probe-{payload.index}")
            for payload in active
        ]
        active_tasks = [
            asyncio.create_task(
                collect_request(
                    engine,
                    prompt_token_ids=payload.prompt_token_ids,
                    request_id=trace.request_id,
                    max_tokens=32,
                    trace=trace,
                )
            )
            for payload, trace in zip(active, active_traces)
        ]
        lead_offset = float(preflight["lead_offset_seconds"])
        await asyncio.sleep(lead_offset)
        r1_arrival_monotonic = time.monotonic()
        active_decode_alive = sum(trace.decode_active for trace in active_traces)
        active_prefill_complete = sum(trace.first_token_monotonic is not None for trace in active_traces)
        source_cursor = recorder.cursor()
        r1_output, r1_trace = await collect_request(
            engine,
            prompt_token_ids=canonical["prompt_token_ids"],
            request_id=f"a02-o{item.ordinal:03d}-r1",
            max_tokens=1,
        )
        active_results = list(await asyncio.gather(*active_tasks))
        await asyncio.sleep(0.2)
        source_records = recorder.since(source_cursor)
        source = _source_summary(source_records)
        connector_stats = sum_connector_records(source_records)
        r1 = _output_record(r1_output, r1_trace)
        foreground = evaluate_foreground(
            anchor=anchor,
            r0_prompt_token_ids=r0["prompt_token_ids"],
            r0_completion_token_ids=r0["completion_token_ids"],
            r1_prompt_token_ids=r1["prompt_token_ids"],
            r0_span=canonical["r0_span"],
            r1_span=canonical["r1_span"],
            r0_cached_tokens=r0["num_cached_tokens"],
            r1_cached_tokens=r1["num_cached_tokens"],
        )
        source_observable = (
            active_prefill_complete == len(active)
            and source["total_prompt_tokens"] == len(r1["prompt_token_ids"])
        )
        local_cached = source["local_cached_tokens"] if source_observable else None
        external_cached = source["external_cached_tokens"] if source_observable else None
        verdict = decide_run(
            foreground_status=foreground.status,
            policy=item.policy,
            target_prefix_tokens=item.length,
            total_cached_tokens=foreground.total_cached_tokens if foreground.total_cached_tokens is not None else -1,
            local_cached_tokens=local_cached,
            external_cached_tokens=external_cached,
            builder_target_blocks=int(cell["builder_target_blocks"]),
            builder_observed_blocks=sum(payload.blocks for payload in plan),
            active_probe_decode_alive=active_decode_alive,
            connector_load_bytes=int(connector_stats.get("load_bytes", 0)),
            transfer_overlap_observable=False,
        )

        config = engine.vllm_config
        connector_config = config.kv_transfer_config
        manifest = {
            "experiment": "A0.2-stock-sufficiency",
            "gate": "comparative-matrix",
            "status": verdict.status,
            "ordinal": item.ordinal,
            "attempt": attempt,
            "schedule_item": asdict(item),
            "schedule_sha256": schedule_sha256(registered_schedule()),
            "argv": list(sys.argv),
            "project_head": project_head,
            "tracked_input_sha256": dict(input_hashes),
            "calibration_sha256": _sha256(CALIBRATION),
            "preflight_sha256": _sha256(PREFLIGHT / "verdict.json"),
            "fixture_sha256": _sha256(fixture_path),
            "anchor_sha256": _sha256(anchor_path),
            "layout": os.environ.get("VLLM_KV_CACHE_LAYOUT"),
            "model_snapshot": model_snapshot,
            "vllm_distribution_version": importlib_metadata.version("vllm"),
            "engine": {
                "prefix_caching": config.cache_config.enable_prefix_caching,
                "chunked_prefill": config.scheduler_config.enable_chunked_prefill,
                "block_size": config.cache_config.block_size,
                "gpu_capacity_blocks": config.cache_config.num_gpu_blocks,
                "connector": None if connector_config is None else connector_config.kv_connector,
                "connector_extra_config": {}
                if connector_config is None
                else dict(connector_config.kv_connector_extra_config),
            },
            "gpu": a01r._gpu_provenance(),
        }
        foreground_artifact = {
            "anchor": anchor,
            "r0": r0,
            "r1": r1,
            "r0_span": canonical["r0_span"],
            "r1_span": canonical["r1_span"],
            "tool_call_id": canonical["tool_call_id"],
            "parser_structures_equal": canonical["r0_tool"] == canonical["r1_tool"],
            "source_observable": source_observable,
            "prompt_sources": source,
            "foreground_observation": asdict(foreground),
        }
        workload = {
            "cell": cell,
            "nonce": item.nonce,
            "payload_plan_sha256": plan_hash,
            "target_background_blocks": cell["builder_target_blocks"],
            "observed_background_blocks": sum(payload.blocks for payload in plan),
            "builder_completed_blocks": sum(payload.blocks for payload in builders),
            "active_probe_prompt_blocks": sum(payload.blocks for payload in active),
            "builder_request_count": len(builders),
            "active_probe_count": len(active),
            "payloads": [
                {
                    "index": payload.index,
                    "role": payload.role,
                    "blocks": payload.blocks,
                    "prompt_sha256": payload.prompt_sha256,
                    "first_block_sha256": payload.first_block_sha256,
                }
                for payload in plan
            ],
            "builder_traces": [trace.as_dict() for _, trace in builder_results],
        }
        probe = {
            "lead_offset_seconds": lead_offset,
            "r1_arrival_monotonic": r1_arrival_monotonic,
            "decode_active_at_r1": active_decode_alive,
            "prefill_complete_at_r1": active_prefill_complete,
            "traces": [trace.as_dict() for _, trace in active_results],
            "request_timings": [request_timing(getattr(output, "metrics", None)) for output, _ in active_results],
            "completion_token_counts": [len(_output_ids(output.outputs[0], "token_ids")) for output, _ in active_results],
        }
        connector = {
            "status": "disabled" if item.policy == "S0" else "enabled",
            "resolved_connector": None if connector_config is None else connector_config.kv_connector,
            "stats_after_r1": connector_stats,
            "transfer_overlap_observable": False,
        }
        timing = {
            "r0": r0["timing"],
            "r1": r1["timing"],
            "barrier_elapsed_seconds": r1_arrival_monotonic - float(r0_trace.finish_monotonic),
            "active_probe_queue_plus_prefill_seconds": [
                request_timing(getattr(output, "metrics", None))["ttft_seconds"]
                for output, _ in active_results
            ],
        }
        return {
            "manifest.json": manifest,
            "foreground.json": foreground_artifact,
            "workload.json": workload,
            "probe.json": probe,
            "connector.json": connector,
            "timing.json": timing,
            "verdict.json": {
                **asdict(verdict),
                "foreground_path": verdict.foreground_path,
                "total_cached_tokens": foreground.total_cached_tokens,
                "local_cached_tokens": local_cached,
                "external_cached_tokens": external_cached,
                "recomputed_prefix_tokens": foreground.recomputed_prefix_tokens,
            },
        }
    finally:
        engine.shutdown()


def _invalid_bundle(item: ScheduleItem, attempt: int, error: Exception) -> dict[str, Any]:
    failure = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }
    return {
        "manifest.json": {
            "experiment": "A0.2-stock-sufficiency",
            "gate": "comparative-matrix",
            "status": "invalid_run",
            "ordinal": item.ordinal,
            "attempt": attempt,
            "schedule_item": asdict(item),
        },
        "foreground.json": {"failure": failure},
        "workload.json": {"failure": failure},
        "probe.json": {"failure": failure},
        "connector.json": {"failure": failure},
        "timing.json": {"failure": failure},
        "verdict.json": {"status": "invalid_run", "reason": str(error)},
    }


def run_matrix(ordinal: int, attempt: int, destination: Path) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    if os.environ.get("VLLM_KV_CACHE_LAYOUT") != "HND":
        raise RuntimeError("matrix requires VLLM_KV_CACHE_LAYOUT=HND before vLLM import")
    item = schedule_item(ordinal)
    calibration, preflight = _load_gate_artifacts()
    input_hashes, project_head = _tracked_inputs(item)
    try:
        bundle = asyncio.run(
            _execute(item, attempt, calibration, preflight, input_hashes, project_head)
        )
    except Exception as error:
        bundle = _invalid_bundle(item, attempt, error)
    write_bundle(destination, bundle)
    return str(bundle["verdict.json"]["status"])


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    os.environ.setdefault("VLLM_KV_CACHE_LAYOUT", "HND")
    item = schedule_item(args.ordinal)
    status = run_matrix(
        args.ordinal,
        args.attempt,
        destination_for(RAW_ROOT, item, args.attempt),
    )
    print(
        f"A0.2 matrix ordinal={args.ordinal} policy={item.policy} "
        f"L={item.length} band={item.band} pair={item.pair} status={status}"
    )
    return 0 if status == "valid_observation" else 1


if __name__ == "__main__":
    raise SystemExit(main())
