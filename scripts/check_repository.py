#!/usr/bin/env python3
"""Validate the dependency-free repository and Phase 0 input contract."""

import json
from pathlib import Path
from typing import Any, Dict

from toolgap_kv.phase0 import LifecycleAction, ObservedAction, ToolGapEvent


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "CONTEXT.md",
    "docs/agent-kv/FIRST_PRINCIPLES.md",
    "docs/agent-kv/PROJECT.md",
    "docs/agent-kv/ARCHITECTURE.md",
    "docs/agent-kv/ROADMAP.md",
    "docs/agent-kv/EVALUATION.md",
    "docs/agent-kv/INTERVIEW_MAP.md",
    "docs/agent-kv/DECISIONS.md",
    "configs/phase0.json",
    "experiments/0001-mechanism-feasibility/manifest.json",
    "experiments/0001-mechanism-feasibility/workload.json",
    "experiments/0001-mechanism-feasibility/raw/.gitkeep",
    "patches/README.md",
)

EXPECTED_OBSERVED_BY_REQUESTED = {
    LifecycleAction.RETAIN: ObservedAction.GPU_HIT,
    LifecycleAction.OFFLOAD: ObservedAction.CPU_RESTORE,
    LifecycleAction.RECOMPUTE: ObservedAction.RECOMPUTE,
}

REQUIRED_EVIDENCE_BY_OBSERVED = {
    ObservedAction.GPU_HIT: {
        "queue_timing",
        "gpu_hit_tokens",
        "resume_first_token_ns",
        "output_token_hash",
    },
    ObservedAction.CPU_RESTORE: {
        "queue_timing",
        "store_start_ns",
        "store_end_ns",
        "gpu_miss_tokens",
        "cpu_hit_tokens",
        "restore_start_ns",
        "restore_end_ns",
        "resume_first_token_ns",
        "output_token_hash",
    },
    ObservedAction.RECOMPUTE: {
        "queue_timing",
        "gpu_miss_tokens",
        "cpu_miss_tokens",
        "prefill_start_ns",
        "prefill_end_ns",
        "resume_first_token_ns",
        "output_token_hash",
    },
}


def load_json(relative_path: str) -> Dict[str, Any]:
    path = ROOT / relative_path
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(relative_path))
    return value


def check_required_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
    if missing:
        raise ValueError("missing required paths: {}".format(", ".join(missing)))


def check_config() -> None:
    config = load_json("configs/phase0.json")
    if config.get("schema_version") != 0:
        raise ValueError("configs/phase0.json must use schema_version 0")
    if config.get("engine", {}).get("pin_status") != "pending_hook_capability_audit":
        raise ValueError("vLLM must remain unpinned until the capability audit")
    if config.get("runtime", {}).get("tensor_parallel_size") != 1:
        raise ValueError("Phase 0 requires tensor_parallel_size 1")
    if config.get("runtime", {}).get("speculative_decoding") is not False:
        raise ValueError("Phase 0 requires speculative decoding to be disabled")


def check_manifest() -> None:
    manifest = load_json(
        "experiments/0001-mechanism-feasibility/manifest.json"
    )
    if manifest.get("experiment_id") != "0001-mechanism-feasibility":
        raise ValueError("unexpected experiment_id")
    claim_state = manifest.get("claim_state")
    raw_data = manifest.get("raw_data", {})
    if claim_state == "roadmap":
        if raw_data.get("status") != "not_collected":
            raise ValueError("roadmap Experiment 0001 must not claim raw data was collected")
        return
    if claim_state != "experimentally validated":
        raise ValueError("Experiment 0001 must be roadmap or experimentally validated")

    expected_scope = (
        "A0.1 only: negative full-block applicability result; A0.2 and A1 are blocked"
    )
    engine = manifest.get("engine", {})
    if (
        manifest.get("result_scope") != expected_scope
        or engine.get("name") != "vllm"
        or not isinstance(engine.get("version"), str)
        or not isinstance(engine.get("commit"), str)
        or engine.get("commit_status") != "pinned_for_A0.1_only"
        or manifest.get("environment", {}).get("status") != "A0.1_executed"
        or raw_data.get("status") != "collected_locally_ignored"
        or not isinstance(raw_data.get("final_run_id"), str)
        or not isinstance(raw_data.get("tracked_summary"), str)
    ):
        raise ValueError("A0.1 negative result must retain its auditable stop boundary")


def check_workload() -> None:
    workload = load_json(
        "experiments/0001-mechanism-feasibility/workload.json"
    )
    if workload.get("schema_version") != 0:
        raise ValueError("workload must use schema_version 0")
    cases = workload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("workload cases must be a non-empty list")

    requested = set()
    observed = set()
    names = set()
    salts = set()
    for case in cases:
        name = case["name"]
        if name in names:
            raise ValueError("duplicate workload case name: {}".format(name))
        names.add(name)
        event = ToolGapEvent.from_mapping(case["event"])
        expected = ObservedAction.parse(case["expected_observed_action"])
        required_observed = EXPECTED_OBSERVED_BY_REQUESTED[event.requested_action]
        if expected is not required_observed:
            raise ValueError(
                "{}: {} must expect {}, got {}".format(
                    name,
                    event.requested_action.value,
                    required_observed.value,
                    expected.value,
                )
            )
        evidence = case.get("required_evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("{} must declare required_evidence".format(name))
        if not all(isinstance(item, str) and item for item in evidence):
            raise ValueError(
                "{} required_evidence entries must be non-empty strings".format(name)
            )
        if "queue_timing" not in evidence:
            raise ValueError(
                "{} must require queue_timing evidence".format(name)
            )
        missing_evidence = REQUIRED_EVIDENCE_BY_OBSERVED[expected] - set(evidence)
        if missing_evidence:
            raise ValueError(
                "{} missing required evidence: {}".format(
                    name, ", ".join(sorted(missing_evidence))
                )
            )
        if event.cache_salt in salts:
            raise ValueError(
                "duplicate cross-case cache_salt: {}".format(event.cache_salt)
            )
        salts.add(event.cache_salt)
        requested.add(event.requested_action)
        observed.add(expected)

    if requested != set(LifecycleAction):
        raise ValueError("workload must request retain, offload, and recompute")
    if observed != set(ObservedAction):
        raise ValueError("workload must expect gpu_hit, cpu_restore, and recompute")


def main() -> None:
    check_required_paths()
    check_config()
    check_manifest()
    check_workload()
    print("repository check: ok")


if __name__ == "__main__":
    main()
