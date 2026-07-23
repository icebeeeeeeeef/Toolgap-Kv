#!/usr/bin/env python3
"""Run one non-comparative A0.2 workload to enforce the GPU-hour cap."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
RAW_ROOT = EXPERIMENT_DIR / "raw"
REPRESENTATIVE_ORDINAL = 42

if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from a02 import decide_budget, write_bundle
from run_matrix import (
    _execute,
    _invalid_bundle,
    _load_gate_artifacts,
    _sha256,
    _tracked_inputs,
    schedule_item,
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
    return raw_root / "budget" / f"representative-S0-a{attempt:02d}"


def _budget_input_hashes(
    item: Any,
) -> tuple[dict[str, str], str]:
    input_hashes, project_head = _tracked_inputs(item)
    runner = Path(__file__).resolve()
    relative = str(runner.relative_to(REPOSITORY_ROOT))
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", relative],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    return ({**input_hashes, relative: _sha256(runner)}, project_head)


def _budget_bundle(
    comparative_bundle: Mapping[str, Any],
    *,
    attempt: int,
    elapsed_seconds: float,
) -> dict[str, Any]:
    run_status = str(comparative_bundle["verdict.json"]["status"])
    budget = decide_budget(representative_run_seconds=elapsed_seconds)
    final_status = budget.status if run_status == "valid_observation" else run_status

    bundle = {name: dict(value) for name, value in comparative_bundle.items()}
    bundle["manifest.json"].update(
        {
            "gate": "budget-dry-run",
            "status": final_status,
            "attempt": attempt,
            "non_comparative": True,
            "representative_ordinal": REPRESENTATIVE_ORDINAL,
        }
    )
    bundle["timing.json"]["budget"] = {
        "representative_run_seconds": elapsed_seconds,
        "comparative_runs": 90,
        "conservative_multiplier": 1.25,
        "cap_gpu_hours": 12.0,
        "predicted_gpu_hours": budget.predicted_gpu_hours,
    }
    bundle["verdict.json"] = {
        "status": final_status,
        "reason": budget.reason if run_status == "valid_observation" else comparative_bundle["verdict.json"]["reason"],
        "representative_run_status": run_status,
        "predicted_gpu_hours": budget.predicted_gpu_hours,
        "non_comparative": True,
    }
    return bundle


def run_budget(attempt: int, destination: Path) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    if os.environ.get("VLLM_KV_CACHE_LAYOUT") != "HND":
        raise RuntimeError("budget dry-run requires VLLM_KV_CACHE_LAYOUT=HND before vLLM import")

    item = schedule_item(REPRESENTATIVE_ORDINAL)
    if item.policy != "S0" or item.length != 8192 or item.band != "target":
        raise RuntimeError("registered representative ordinal drifted")
    calibration, preflight = _load_gate_artifacts()
    input_hashes, project_head = _budget_input_hashes(item)

    started = time.monotonic()
    try:
        comparative_bundle = asyncio.run(
            _execute(item, attempt, calibration, preflight, input_hashes, project_head)
        )
    except Exception as error:
        comparative_bundle = _invalid_bundle(item, attempt, error)
    elapsed = time.monotonic() - started
    bundle = _budget_bundle(
        comparative_bundle,
        attempt=attempt,
        elapsed_seconds=elapsed,
    )
    write_bundle(destination, bundle)
    return str(bundle["verdict.json"]["status"])


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    os.environ.setdefault("VLLM_KV_CACHE_LAYOUT", "HND")
    destination = destination_for(RAW_ROOT, args.attempt)
    status = run_budget(args.attempt, destination)
    print(f"A0.2 budget dry-run status={status} destination={destination}")
    return 0 if status == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
