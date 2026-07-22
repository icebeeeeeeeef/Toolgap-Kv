#!/usr/bin/env python3
"""Run the non-comparative HND capacity calibration for A0.2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as importlib_metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
QUALIFICATION_DIR = REPOSITORY_ROOT / "experiments/A0.2-foreground-length-qualification"
A01R_RUNNER = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual/run_task0.py"
SPEC = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/A0.2-stock-sufficiency-spec.md"
DESIGN = REPOSITORY_ROOT / "docs/superpowers/specs/2026-07-22-a02-stock-sufficiency-design.md"
RAW_ROOT = EXPERIMENT_DIR / "raw"
BLOCK_SIZE = 16
PAYLOAD_BLOCK_CAP = 128
ACTIVE_PROBE_COUNT = 16

if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from a02 import LENGTHS, build_calibration, registered_schedule, schedule_sha256
from payloads import build_payload_plan, payload_plan_sha256


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
    return raw_root / "calibration" / f"calibration-a{attempt:02d}" / "calibration.json"


def engine_kwargs(model_snapshot: str) -> dict[str, Any]:
    return {
        "model": model_snapshot,
        "tokenizer": model_snapshot,
        "tensor_parallel_size": 1,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "block_size": BLOCK_SIZE,
        "max_model_len": 32768,
        "max_num_seqs": 64,
        "max_num_batched_tokens": 32768,
        "gpu_memory_utilization": 0.9,
        "seed": 0,
        "disable_log_stats": False,
    }


def kv_block_bytes(
    *,
    num_layers: int,
    num_kv_heads: int,
    head_size: int,
    element_size: int,
    block_size: int,
) -> int:
    values = (num_layers, num_kv_heads, head_size, element_size, block_size)
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError("KV block dimensions must be positive integers")
    return num_layers * 2 * num_kv_heads * head_size * element_size * block_size


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


def _tracked_inputs() -> tuple[dict[str, str], str]:
    paths = [
        EXPERIMENT_DIR / "a02.py",
        EXPERIMENT_DIR / "payloads.py",
        EXPERIMENT_DIR / "run_calibration.py",
        SPEC,
        DESIGN,
        A01R_RUNNER,
    ]
    paths.extend(QUALIFICATION_DIR / "anchors" / f"foreground-{length}.json" for length in LENGTHS)
    paths.extend(QUALIFICATION_DIR / "fixtures" / f"foreground-{length}.json" for length in LENGTHS)
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


def _write_immutable_json(destination: Path, value: Mapping[str, Any]) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".calibration-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _usable_token_ids(tokenizer: Any) -> list[int]:
    vocab_size = int(tokenizer.vocab_size)
    special_ids = {int(value) for value in getattr(tokenizer, "all_special_ids", [])}
    ids = [value for value in range(256, min(vocab_size, 65536)) if value not in special_ids]
    if len(ids) < 256:
        raise RuntimeError("tokenizer did not expose enough non-special token IDs")
    return ids


def _model_shape(config: Any) -> dict[str, int]:
    hf_config = config.model_config.hf_text_config
    num_layers = int(hf_config.num_hidden_layers)
    num_kv_heads = int(hf_config.num_key_value_heads)
    head_size = int(getattr(hf_config, "head_dim", hf_config.hidden_size // hf_config.num_attention_heads))
    import torch

    element_size = int(torch.empty((), dtype=config.model_config.dtype).element_size())
    return {
        "num_layers": num_layers,
        "num_kv_heads": num_kv_heads,
        "head_size": head_size,
        "element_size": element_size,
    }


def _payload_calibration(
    *,
    calibration: Mapping[str, Any],
    tokenizer: Any,
    a01r: Any,
) -> list[dict[str, Any]]:
    usable_ids = _usable_token_ids(tokenizer)
    cells = {(cell["length"], cell["band"]): cell for cell in calibration["cells"]}
    summaries: list[dict[str, Any]] = []
    for item in registered_schedule()[::2]:
        fixture = json.loads(
            (QUALIFICATION_DIR / "fixtures" / f"foreground-{item.length}.json").read_text(encoding="utf-8")
        )
        foreground_ids = a01r._render_ids(tokenizer, fixture["initial_messages"], fixture["tools"])
        cell = cells[(item.length, item.band)]
        plan = build_payload_plan(
            total_blocks=int(cell["builder_target_blocks"]),
            block_size=int(calibration["block_size"]),
            nonce=item.nonce,
            usable_token_ids=usable_ids,
            foreground_first_block=foreground_ids[: int(calibration["block_size"])],
            payload_block_cap=PAYLOAD_BLOCK_CAP,
            active_probe_count=ACTIVE_PROBE_COUNT,
        )
        summaries.append(
            {
                "length": item.length,
                "band": item.band,
                "pair": item.pair,
                "nonce": item.nonce,
                "builder_target_blocks": cell["builder_target_blocks"],
                "payload_count": len(plan),
                "builder_request_count": sum(payload.role == "builder" for payload in plan),
                "active_probe_count": sum(payload.role == "active_probe" for payload in plan),
                "payload_plan_sha256": payload_plan_sha256(plan),
            }
        )
    return summaries


def run_calibration(attempt: int, destination: Path) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    if os.environ.get("VLLM_KV_CACHE_LAYOUT") != "HND":
        raise RuntimeError("calibration requires VLLM_KV_CACHE_LAYOUT=HND before vLLM import")
    input_hashes, project_head = _tracked_inputs()
    a01r = _load_module(A01R_RUNNER, "a02_calibration_a01r")

    import psutil
    import vllm
    from huggingface_hub import snapshot_download
    from vllm import LLM

    distribution_version = importlib_metadata.version("vllm")
    a01r._require_vllm_version()
    vllm_commit, vllm_source_root = a01r._pinned_vllm_commit(vllm)
    model_snapshot = a01r._local_model_snapshot(snapshot_download)
    llm = LLM(**engine_kwargs(model_snapshot))
    config = llm.llm_engine.vllm_config
    if config.cache_config.enable_prefix_caching is not True:
        raise RuntimeError("engine did not preserve prefix caching")
    if config.scheduler_config.enable_chunked_prefill is not True:
        raise RuntimeError("engine did not preserve chunked prefill")
    if config.cache_config.block_size != BLOCK_SIZE:
        raise RuntimeError("resolved block size differs from registered block size")
    capacity = config.cache_config.num_gpu_blocks
    if type(capacity) is not int or capacity <= 0:
        raise RuntimeError("engine did not expose positive num_gpu_blocks")
    shape = _model_shape(config)
    block_bytes = kv_block_bytes(block_size=BLOCK_SIZE, **shape)
    calibration = build_calibration(
        gpu_capacity_blocks=capacity,
        block_size=BLOCK_SIZE,
        block_bytes=block_bytes,
        host_available_bytes=int(psutil.virtual_memory().available),
    )
    payload_summaries: list[dict[str, Any]] = []
    if calibration["status"] == "valid":
        payload_summaries = _payload_calibration(
            calibration=calibration,
            tokenizer=llm.get_tokenizer(),
            a01r=a01r,
        )
    artifact = {
        **calibration,
        "experiment": "A0.2-stock-sufficiency",
        "gate": "calibration",
        "attempt": attempt,
        "project_head": project_head,
        "tracked_input_sha256": input_hashes,
        "schedule_sha256": schedule_sha256(registered_schedule()),
        "layout": os.environ["VLLM_KV_CACHE_LAYOUT"],
        "engine_kwargs": engine_kwargs(model_snapshot),
        "model_shape": shape,
        "payload_block_cap": PAYLOAD_BLOCK_CAP,
        "active_probe_count": ACTIVE_PROBE_COUNT,
        "payload_plans": payload_summaries,
        "vllm": {
            "distribution_version": distribution_version,
            "commit": vllm_commit,
            "source_root": vllm_source_root,
        },
        "gpu": a01r._gpu_provenance(),
    }
    _write_immutable_json(destination, artifact)
    return str(calibration["status"])


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    os.environ.setdefault("VLLM_KV_CACHE_LAYOUT", "HND")
    status = run_calibration(args.attempt, destination_for(RAW_ROOT, args.attempt))
    print(f"A0.2 calibration attempt={args.attempt} status={status}")
    return 0 if status == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
