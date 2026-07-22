#!/usr/bin/env python3
"""Run A0.2 native-connector and active-probe timing preflights."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
RAW_ROOT = EXPERIMENT_DIR / "raw"
CALIBRATION = RAW_ROOT / "calibration/calibration-a01/calibration.json"
A01R_RUNNER = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual/run_task0.py"
SPEC = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/A0.2-stock-sufficiency-spec.md"
DESIGN = REPOSITORY_ROOT / "docs/superpowers/specs/2026-07-22-a02-stock-sufficiency-design.md"
WORKER_ENV = "TOOLGAP_A02_PREFLIGHT_WORKER"
WORKER_MARKER = "A02_PREFLIGHT_WORKER_JSON="
PREFLIGHT_FILES = {"manifest.json", "connector.json", "probe-timing.json", "verdict.json"}

if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from a02 import (
    decide_connector_preflight,
    decide_probe_preflight,
    select_probe_lead_offset,
)
from payloads import build_payload_plan, payload_plan_sha256
from run_calibration import ACTIVE_PROBE_COUNT, BLOCK_SIZE, PAYLOAD_BLOCK_CAP, engine_kwargs
from runtime import (
    EvidenceRecorder,
    RequestTrace,
    collect_request,
    run_requests,
    stat_logger_factory,
    sum_connector_records,
    summarize_prompt_sources,
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args(argv)
    if args.attempt <= 0:
        parser.error("--attempt must be positive")
    return args


def destination_for(raw_root: Path, attempt: int) -> Path:
    if attempt <= 0:
        raise ValueError("attempt must be positive")
    return raw_root / "preflight" / f"preflight-a{attempt:02d}"


def policy_engine_kwargs(model_snapshot: str, policy: str, offloading_size_gib: int) -> dict[str, Any]:
    kwargs = engine_kwargs(model_snapshot)
    if policy == "S0":
        return kwargs
    if policy != "S1" or type(offloading_size_gib) is not int or offloading_size_gib <= 0:
        raise ValueError("policy must be S0 or S1 with a positive S1 offloading size")
    return {
        **kwargs,
        "kv_offloading_size": offloading_size_gib,
        "kv_offloading_backend": "native",
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


def _load_calibration() -> dict[str, Any]:
    value = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    if value.get("status") != "valid":
        raise RuntimeError("A0.2 calibration is absent or not valid")
    if value.get("layout") != "HND" or value.get("block_size") != BLOCK_SIZE:
        raise RuntimeError("A0.2 calibration layout/block size drifted")
    return value


def _tracked_inputs() -> tuple[dict[str, str], str]:
    paths = (
        EXPERIMENT_DIR / "a02.py",
        EXPERIMENT_DIR / "payloads.py",
        EXPERIMENT_DIR / "runtime.py",
        EXPERIMENT_DIR / "run_calibration.py",
        EXPERIMENT_DIR / "run_preflight.py",
        SPEC,
        DESIGN,
        A01R_RUNNER,
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


def _usable_token_ids(tokenizer: Any) -> list[int]:
    special = {int(value) for value in getattr(tokenizer, "all_special_ids", [])}
    ids = [value for value in range(256, min(int(tokenizer.vocab_size), 65536)) if value not in special]
    if len(ids) < 256:
        raise RuntimeError("tokenizer exposed too few non-special IDs")
    return ids


def _worker_engine(policy: str, calibration: Mapping[str, Any]) -> tuple[Any, EvidenceRecorder, Any, str]:
    if os.environ.get("VLLM_KV_CACHE_LAYOUT") != "HND":
        raise RuntimeError("preflight worker requires VLLM_KV_CACHE_LAYOUT=HND")
    a01r = _load_module(A01R_RUNNER, f"a02_preflight_a01r_{policy}")
    import vllm
    from huggingface_hub import snapshot_download
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.v1.engine.async_llm import AsyncLLM

    a01r._require_vllm_version()
    a01r._pinned_vllm_commit(vllm)
    model_snapshot = a01r._local_model_snapshot(snapshot_download)
    recorder = EvidenceRecorder()
    args = AsyncEngineArgs(
        **policy_engine_kwargs(
            model_snapshot,
            policy,
            int(calibration["s1_kv_offloading_size_gib"]),
        )
    )
    engine = AsyncLLM.from_engine_args(args, stat_loggers=[stat_logger_factory(recorder)])
    return engine, recorder, a01r, model_snapshot


def _source_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    source_records = [
        record["prompt_sources"]
        for record in records
        if isinstance(record.get("prompt_sources"), Mapping)
        and int(record["prompt_sources"].get("total", 0)) > 0
    ]
    return summarize_prompt_sources(source_records)


async def _connector_worker(attempt: int, calibration: Mapping[str, Any]) -> dict[str, Any]:
    engine, recorder, _, _ = _worker_engine("S1", calibration)
    try:
        config = engine.vllm_config
        connector_config = config.kv_transfer_config
        resolved_connector = None if connector_config is None else connector_config.kv_connector
        extra = {} if connector_config is None else dict(connector_config.kv_connector_extra_config)
        configured_cpu_bytes = int(extra.get("cpu_bytes_to_use", 0))
        capacity = int(config.cache_config.num_gpu_blocks or 0)
        tokenizer = engine.get_tokenizer()
        usable_ids = _usable_token_ids(tokenizer)
        warm = build_payload_plan(
            total_blocks=2048 // BLOCK_SIZE,
            block_size=BLOCK_SIZE,
            nonce=f"connector-warm-a{attempt}",
            usable_token_ids=usable_ids,
            foreground_first_block=usable_ids[-BLOCK_SIZE:],
            payload_block_cap=2048 // BLOCK_SIZE,
            active_probe_count=1,
        )[0]
        warm_output, warm_trace = await collect_request(
            engine,
            prompt_token_ids=warm.prompt_token_ids,
            request_id=f"a02-connector-warm-a{attempt}",
            max_tokens=1,
        )
        target_cell = next(
            cell for cell in calibration["cells"] if cell["length"] == 2048 and cell["band"] == "target"
        )
        pressure = build_payload_plan(
            total_blocks=int(target_cell["builder_target_blocks"]),
            block_size=BLOCK_SIZE,
            nonce=f"connector-pressure-a{attempt}",
            usable_token_ids=usable_ids,
            foreground_first_block=warm.prompt_token_ids[:BLOCK_SIZE],
            payload_block_cap=PAYLOAD_BLOCK_CAP,
            active_probe_count=ACTIVE_PROBE_COUNT,
        )
        await run_requests(
            engine,
            [
                (payload.prompt_token_ids, f"a02-connector-builder-a{attempt}-{payload.index}", 1)
                for payload in pressure
            ],
        )
        await asyncio.sleep(0.5)
        cursor = recorder.cursor()
        resume_output, resume_trace = await collect_request(
            engine,
            prompt_token_ids=warm.prompt_token_ids,
            request_id=f"a02-connector-resume-a{attempt}",
            max_tokens=1,
        )
        await asyncio.sleep(0.5)
        records = recorder.since(cursor)
        source = _source_summary(records)
        connector = sum_connector_records(records)
        if source["total_cached_tokens"] != int(getattr(resume_output, "num_cached_tokens", -1)):
            raise RuntimeError("custom source accounting differs from RequestOutput.num_cached_tokens")
        verdict = decide_connector_preflight(
            resolved_connector=resolved_connector,
            gpu_capacity_blocks=capacity,
            expected_gpu_capacity_blocks=int(calibration["gpu_capacity_blocks"]),
            configured_cpu_bytes=configured_cpu_bytes,
            required_cpu_bytes=int(calibration["s1_required_cpu_bytes"]),
            external_cached_tokens=source["external_cached_tokens"],
            connector_load_bytes=int(connector.get("load_bytes", 0)),
        )
        return {
            "status": verdict.status,
            "reason": verdict.reason,
            "transfer_overlap_observable": verdict.transfer_overlap_observable,
            "resolved_connector": resolved_connector,
            "resolved_cpu_bytes_to_use": configured_cpu_bytes,
            "resolved_cpu_block_capacity": configured_cpu_bytes // int(calibration["block_bytes"]),
            "resolved_gpu_capacity_blocks": capacity,
            "warm_num_cached_tokens": getattr(warm_output, "num_cached_tokens", None),
            "resume_num_cached_tokens": getattr(resume_output, "num_cached_tokens", None),
            "prompt_sources": source,
            "connector_stats": connector,
            "warm_trace": warm_trace.as_dict(),
            "resume_trace": resume_trace.as_dict(),
            "pressure": {
                "target_blocks": target_cell["builder_target_blocks"],
                "observed_blocks": sum(payload.blocks for payload in pressure),
                "payload_count": len(pressure),
                "payload_plan_sha256": payload_plan_sha256(pressure),
            },
        }
    finally:
        engine.shutdown()


def _probe_payloads(tokenizer: Any, nonce: str) -> tuple[Any, ...]:
    usable_ids = _usable_token_ids(tokenizer)
    return build_payload_plan(
        total_blocks=ACTIVE_PROBE_COUNT,
        block_size=BLOCK_SIZE,
        nonce=nonce,
        usable_token_ids=usable_ids,
        foreground_first_block=usable_ids[-BLOCK_SIZE:],
        payload_block_cap=1,
        active_probe_count=ACTIVE_PROBE_COUNT,
    )


async def _start_probe_wave(engine: Any, tokenizer: Any, nonce: str) -> tuple[list[asyncio.Task[Any]], list[RequestTrace], str]:
    payloads = _probe_payloads(tokenizer, nonce)
    traces = [RequestTrace(request_id=f"{nonce}-{payload.index}") for payload in payloads]
    tasks = [
        asyncio.create_task(
            collect_request(
                engine,
                prompt_token_ids=payload.prompt_token_ids,
                request_id=trace.request_id,
                max_tokens=32,
                trace=trace,
            )
        )
        for payload, trace in zip(payloads, traces)
    ]
    return tasks, traces, payload_plan_sha256(payloads)


async def _probe_worker(attempt: int, calibration: Mapping[str, Any]) -> dict[str, Any]:
    engine, _, _, _ = _worker_engine("S0", calibration)
    try:
        tokenizer = engine.get_tokenizer()
        pilot_tasks, pilot_traces, pilot_hash = await _start_probe_wave(
            engine, tokenizer, f"a02-probe-pilot-a{attempt}"
        )
        await asyncio.gather(*pilot_tasks)
        first_delays = [trace.as_dict()["first_token_delay_seconds"] for trace in pilot_traces]
        finish_delays = [trace.as_dict()["finish_delay_seconds"] for trace in pilot_traces]
        if any(value is None for value in first_delays + finish_delays):
            raise RuntimeError("pilot did not produce complete first/finish timings")
        lead_offset = select_probe_lead_offset(
            first_token_delays=[float(value) for value in first_delays],
            finish_delays=[float(value) for value in finish_delays],
        )
        trials: list[dict[str, Any]] = []
        for trial in range(1, 11):
            tasks, traces, plan_hash = await _start_probe_wave(
                engine, tokenizer, f"a02-probe-validation-a{attempt}-t{trial:02d}"
            )
            await asyncio.sleep(lead_offset)
            alive = sum(trace.decode_active for trace in traces)
            r1_arrival_monotonic = __import__("time").monotonic()
            await asyncio.gather(*tasks)
            trials.append(
                {
                    "trial": trial,
                    "lead_offset_seconds": lead_offset,
                    "r1_arrival_monotonic": r1_arrival_monotonic,
                    "active_probe_decode_alive": alive,
                    "payload_plan_sha256": plan_hash,
                    "traces": [trace.as_dict() for trace in traces],
                }
            )
        verdict = decide_probe_preflight([trial["active_probe_decode_alive"] for trial in trials])
        return {
            "status": verdict.status,
            "reason": verdict.reason,
            "live_trials": verdict.live_trials,
            "lead_offset_seconds": lead_offset,
            "pilot_payload_plan_sha256": pilot_hash,
            "pilot_traces": [trace.as_dict() for trace in pilot_traces],
            "trials": trials,
        }
    finally:
        engine.shutdown()


def _run_worker(mode: str, attempt: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment[WORKER_ENV] = mode
    environment["VLLM_KV_CACHE_LAYOUT"] = "HND"
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--attempt", str(attempt)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    payload = None
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(WORKER_MARKER):
            payload = json.loads(line[len(WORKER_MARKER) :])
            break
    if completed.returncode != 0 or not isinstance(payload, dict):
        return {
            "status": "invalid_run",
            "reason": f"{mode} worker failed with returncode={completed.returncode}",
            "stdout_tail": completed.stdout[-8000:],
            "stderr_tail": completed.stderr[-8000:],
        }
    payload["stdout_tail"] = completed.stdout[-8000:]
    payload["stderr_tail"] = completed.stderr[-8000:]
    return payload


def _write_preflight_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    if set(files) != PREFLIGHT_FILES:
        raise ValueError("preflight bundle must contain exactly four files")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".a02-preflight-", dir=destination.parent))
    try:
        for name, value in files.items():
            (temporary / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def run_preflight(attempt: int, destination: Path) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    calibration = _load_calibration()
    input_hashes, project_head = _tracked_inputs()
    connector = _run_worker("connector", attempt)
    probe = _run_worker("probe", attempt) if connector.get("status") == "valid" else {
        "status": "not_run",
        "reason": "connector preflight did not pass",
    }
    status = "valid" if connector.get("status") == "valid" and probe.get("status") == "valid" else str(
        connector.get("status") if connector.get("status") != "valid" else probe.get("status")
    )
    manifest = {
        "experiment": "A0.2-stock-sufficiency",
        "gate": "connector-and-probe-preflight",
        "attempt": attempt,
        "status": status,
        "project_head": project_head,
        "tracked_input_sha256": input_hashes,
        "calibration_path": str(CALIBRATION.relative_to(REPOSITORY_ROOT)),
        "calibration_sha256": _sha256(CALIBRATION),
        "layout": "HND",
    }
    _write_preflight_bundle(
        destination,
        {
            "manifest.json": manifest,
            "connector.json": connector,
            "probe-timing.json": probe,
            "verdict.json": {
                "status": status,
                "connector_status": connector.get("status"),
                "probe_status": probe.get("status"),
                "transfer_overlap_observable": False,
                "lead_offset_seconds": probe.get("lead_offset_seconds"),
            },
        },
    )
    return status


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    worker = os.environ.get(WORKER_ENV)
    if worker in {"connector", "probe"}:
        calibration = _load_calibration()
        try:
            result = asyncio.run(
                _connector_worker(args.attempt, calibration)
                if worker == "connector"
                else _probe_worker(args.attempt, calibration)
            )
        except Exception as error:
            result = {"status": "invalid_run", "reason": f"{type(error).__name__}: {error}"}
            print(WORKER_MARKER + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            return 1
        print(WORKER_MARKER + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0 if result.get("status") == "valid" else 1

    os.environ.setdefault("VLLM_KV_CACHE_LAYOUT", "HND")
    status = run_preflight(args.attempt, destination_for(RAW_ROOT, args.attempt))
    print(f"A0.2 preflight attempt={args.attempt} status={status}")
    return 0 if status == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
