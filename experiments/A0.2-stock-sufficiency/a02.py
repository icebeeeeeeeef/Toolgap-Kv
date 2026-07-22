"""Pure contracts for the frozen A0.2 stock-sufficiency experiment.

This module deliberately does not import vLLM. GPU runners pass resolved
engine facts into these helpers; the helpers only freeze schedule, capacity
math, verdict inputs, and immutable evidence publication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence


LENGTHS = (2048, 8192, 16384)
BANDS = (
    ("low", 1, 2),
    ("target", 11, 10),
    ("overload", 13, 10),
)
POLICIES = ("S0", "S1")
PAIRS_PER_CELL = 5
SCHEDULE_SEED = "toolgap-kv-a02-stock-sufficiency-v1"
BUNDLE_FILES = {
    "manifest.json",
    "foreground.json",
    "workload.json",
    "probe.json",
    "connector.json",
    "timing.json",
    "verdict.json",
}


@dataclass(frozen=True)
class ScheduleItem:
    ordinal: int
    length: int
    band: str
    m_numerator: int
    m_denominator: int
    pair: int
    policy: str
    order: tuple[str, str]
    nonce: str


@dataclass(frozen=True)
class ForegroundObservation:
    status: str
    reason: str
    total_cached_tokens: int | None
    recomputed_prefix_tokens: int | None


@dataclass(frozen=True)
class RunVerdict:
    status: str
    reason: str
    foreground_path: str


@dataclass(frozen=True)
class ProbePreflightVerdict:
    status: str
    reason: str
    live_trials: int


@dataclass(frozen=True)
class ConnectorPreflightVerdict:
    status: str
    reason: str
    transfer_overlap_observable: bool


def _pair_order(length: int, band: str, pair: int) -> tuple[str, str]:
    material = f"{SCHEDULE_SEED}:{length}:{band}:{pair}".encode("utf-8")
    return ("S0", "S1") if hashlib.sha256(material).digest()[0] % 2 == 0 else ("S1", "S0")


def registered_schedule() -> tuple[ScheduleItem, ...]:
    """Return the only legal 90-run comparative schedule."""
    items: list[ScheduleItem] = []
    ordinal = 1
    for length in LENGTHS:
        for band, numerator, denominator in BANDS:
            for pair in range(1, PAIRS_PER_CELL + 1):
                order = _pair_order(length, band, pair)
                nonce = f"a02-{length}-{band}-p{pair}-{SCHEDULE_SEED}"
                for policy in order:
                    items.append(
                        ScheduleItem(
                            ordinal=ordinal,
                            length=length,
                            band=band,
                            m_numerator=numerator,
                            m_denominator=denominator,
                            pair=pair,
                            policy=policy,
                            order=order,
                            nonce=nonce,
                        )
                    )
                    ordinal += 1
    return tuple(items)


def _compact_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def schedule_sha256(schedule: Sequence[ScheduleItem]) -> str:
    return hashlib.sha256(_compact_json_bytes([asdict(item) for item in schedule])).hexdigest()


def token_ids_sha256(token_ids: Sequence[int]) -> str:
    return hashlib.sha256(
        json.dumps(list(token_ids), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _integer_ids(value: Sequence[int]) -> list[int] | None:
    if not isinstance(value, (list, tuple)) or any(type(token) is not int for token in value):
        return None
    return list(value)


def _span(value: Sequence[int]) -> tuple[int, int] | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(type(index) is not int for index in value)
        or value[0] < 0
        or value[1] <= value[0]
    ):
        return None
    return int(value[0]), int(value[1])


def _lcp(left: Sequence[int], right: Sequence[int]) -> int:
    for index, (left_token, right_token) in enumerate(zip(left, right)):
        if left_token != right_token:
            return index
    return min(len(left), len(right))


def evaluate_foreground(
    *,
    anchor: Mapping[str, Any],
    r0_prompt_token_ids: Sequence[int],
    r0_completion_token_ids: Sequence[int],
    r1_prompt_token_ids: Sequence[int],
    r0_span: Sequence[int],
    r1_span: Sequence[int],
    r0_cached_tokens: int | None,
    r1_cached_tokens: int | None,
) -> ForegroundObservation:
    """Validate the per-L immutable token anchor before interpreting pressure."""
    r0_prompt = _integer_ids(r0_prompt_token_ids)
    r0_completion = _integer_ids(r0_completion_token_ids)
    r1_prompt = _integer_ids(r1_prompt_token_ids)
    observed_r0_span = _span(r0_span)
    observed_r1_span = _span(r1_span)
    anchor_r0_span = _span(anchor.get("r0_span"))
    anchor_r1_span = _span(anchor.get("r1_span"))
    target = anchor.get("target_full_prefix_tokens")
    block_size = anchor.get("block_size")
    expected_lcp = anchor.get("lcp")
    expected_hash = anchor.get("eligible_prefix_sha256")
    if (
        anchor.get("schema_version") != 1
        or type(target) is not int
        or type(block_size) is not int
        or type(expected_lcp) is not int
        or not isinstance(expected_hash, str)
        or r0_prompt is None
        or r0_completion is None
        or r1_prompt is None
        or observed_r0_span is None
        or observed_r1_span is None
        or anchor_r0_span is None
        or anchor_r1_span is None
    ):
        return ForegroundObservation("invalid_run", "malformed foreground anchor evidence", None, None)

    r0_ids = r0_prompt + r0_completion
    observed_lcp = _lcp(r0_ids, r1_prompt)
    spans_in_range = (
        observed_r0_span[1] <= len(r0_ids)
        and observed_r1_span[1] <= len(r1_prompt)
    )
    semantic_equal = spans_in_range and (
        r0_ids[observed_r0_span[0] : observed_r0_span[1]]
        == r1_prompt[observed_r1_span[0] : observed_r1_span[1]]
    )
    anchor_matches = (
        observed_r0_span == anchor_r0_span
        and observed_r1_span == anchor_r1_span
        and observed_lcp == expected_lcp
        and semantic_equal
        and len(r1_prompt) >= target
        and token_ids_sha256(r1_prompt[:target]) == expected_hash
    )
    if r0_cached_tokens != 0 or not anchor_matches:
        reason = "fresh R0 was not cold" if r0_cached_tokens != 0 else "foreground anchor drifted"
        return ForegroundObservation("invalid_run", reason, None, None)

    if (
        type(r1_cached_tokens) is not int
        or r1_cached_tokens < 0
        or r1_cached_tokens > target
        or r1_cached_tokens > len(r1_prompt)
        or r1_cached_tokens % block_size != 0
    ):
        return ForegroundObservation(
            "accounting_contract_change",
            "R1 total cached-token accounting is malformed or outside the registered anchor",
            None,
            None,
        )
    return ForegroundObservation(
        "valid",
        "foreground anchor and total cached-token accounting are valid",
        r1_cached_tokens,
        target - r1_cached_tokens,
    )


def decide_run(
    *,
    foreground_status: str,
    policy: str,
    target_prefix_tokens: int,
    total_cached_tokens: int,
    local_cached_tokens: int | None,
    external_cached_tokens: int | None,
    builder_target_blocks: int,
    builder_observed_blocks: int,
    active_probe_decode_alive: int,
    connector_load_bytes: int,
    transfer_overlap_observable: bool,
) -> RunVerdict:
    """Classify one run without applying cross-run Stop/Continue rules."""
    del transfer_overlap_observable
    if foreground_status != "valid":
        return RunVerdict(foreground_status, "foreground oracle did not validate", "unclassified")
    if policy not in POLICIES:
        return RunVerdict("invalid_run", "unknown policy", "unclassified")
    counters = (target_prefix_tokens, total_cached_tokens, builder_target_blocks, builder_observed_blocks)
    if any(type(value) is not int or value < 0 for value in counters):
        return RunVerdict("accounting_contract_change", "malformed run accounting", "unclassified")
    if type(connector_load_bytes) is not int or connector_load_bytes < 0:
        return RunVerdict("accounting_contract_change", "malformed connector accounting", "unclassified")
    if local_cached_tokens is None and external_cached_tokens is None:
        return RunVerdict(
            "inconclusive",
            "per-request local/external cached-token source is unobservable",
            "source_unobservable",
        )
    if (
        type(local_cached_tokens) is not int
        or type(external_cached_tokens) is not int
        or local_cached_tokens < 0
        or external_cached_tokens < 0
        or local_cached_tokens + external_cached_tokens != total_cached_tokens
        or total_cached_tokens > target_prefix_tokens
        or (policy == "S0" and external_cached_tokens != 0)
    ):
        return RunVerdict(
            "accounting_contract_change",
            "local/external source accounting contradicts total cached tokens or policy",
            "unclassified",
        )
    if builder_observed_blocks != builder_target_blocks or active_probe_decode_alive <= 0:
        return RunVerdict(
            "inconclusive",
            "pressure barrier or active-probe liveness precondition failed",
            "unclassified",
        )
    if external_cached_tokens > 0 and connector_load_bytes <= 0:
        return RunVerdict(
            "inconclusive",
            "external cached tokens lack native connector load evidence",
            "external_unattributed",
        )

    if total_cached_tokens == 0:
        path = "full_recompute"
    elif local_cached_tokens == target_prefix_tokens:
        path = "gpu_local_hit"
    elif external_cached_tokens == target_prefix_tokens:
        path = "cpu_restore"
    elif external_cached_tokens > 0:
        path = "mixed_cpu_restore"
    else:
        path = "partial_gpu_hit"
    return RunVerdict("valid_observation", "run is eligible for cross-run aggregation", path)


def select_probe_lead_offset(
    *,
    first_token_delays: Sequence[float],
    finish_delays: Sequence[float],
) -> float:
    """Freeze one lead offset at the midpoint of the pilot decode window."""
    if (
        not first_token_delays
        or len(first_token_delays) != len(finish_delays)
        or any(not isinstance(value, (int, float)) or value < 0 for value in first_token_delays)
        or any(not isinstance(value, (int, float)) or value <= 0 for value in finish_delays)
    ):
        raise ValueError("pilot timings must be non-empty non-negative numeric pairs")
    decode_start = min(float(value) for value in first_token_delays)
    decode_end = max(float(value) for value in finish_delays)
    if decode_end <= decode_start:
        raise ValueError("pilot did not expose a positive decode-active window")
    return (decode_start + decode_end) / 2


def decide_probe_preflight(active_decode_counts: Sequence[int]) -> ProbePreflightVerdict:
    if len(active_decode_counts) != 10 or any(type(value) is not int or value < 0 for value in active_decode_counts):
        return ProbePreflightVerdict("invalid_run", "probe preflight requires exactly ten valid counts", 0)
    live_trials = sum(value > 0 for value in active_decode_counts)
    if live_trials >= 9:
        return ProbePreflightVerdict("valid", "fixed lead offset kept a probe decode-active in at least 9/10 trials", live_trials)
    return ProbePreflightVerdict("workload_spec_stop", "fixed lead offset failed the registered 9/10 liveness gate", live_trials)


def decide_connector_preflight(
    *,
    resolved_connector: str | None,
    gpu_capacity_blocks: int,
    expected_gpu_capacity_blocks: int,
    configured_cpu_bytes: int,
    required_cpu_bytes: int,
    external_cached_tokens: int | None,
    connector_load_bytes: int,
) -> ConnectorPreflightVerdict:
    values = (
        gpu_capacity_blocks,
        expected_gpu_capacity_blocks,
        configured_cpu_bytes,
        required_cpu_bytes,
        connector_load_bytes,
    )
    if any(type(value) is not int or value < 0 for value in values):
        return ConnectorPreflightVerdict("invalid_configuration", "malformed connector capacity evidence", False)
    if (
        resolved_connector != "OffloadingConnector"
        or gpu_capacity_blocks != expected_gpu_capacity_blocks
        or configured_cpu_bytes < required_cpu_bytes
    ):
        return ConnectorPreflightVerdict("invalid_configuration", "resolved connector, GPU capacity, or CPU tier differs from calibration", False)
    if type(external_cached_tokens) is not int or external_cached_tokens <= 0 or connector_load_bytes <= 0:
        return ConnectorPreflightVerdict("connector_observability_stop", "controlled load did not expose external cached tokens plus load bytes", False)
    return ConnectorPreflightVerdict("valid", "native connector configuration and controlled load are observable", False)


def build_calibration(
    *,
    gpu_capacity_blocks: int,
    block_size: int,
    block_bytes: int,
    host_available_bytes: int,
) -> dict[str, Any]:
    """Freeze capacity arithmetic without producing comparative evidence."""
    for name, value in {
        "gpu_capacity_blocks": gpu_capacity_blocks,
        "block_size": block_size,
        "block_bytes": block_bytes,
        "host_available_bytes": host_available_bytes,
    }.items():
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    reasons: list[str] = []
    cells: list[dict[str, Any]] = []
    for length in LENGTHS:
        if length % block_size:
            reasons.append(f"length={length} is not aligned to block_size={block_size}")
            foreground_blocks = length // block_size
        else:
            foreground_blocks = length // block_size
        for band, numerator, denominator in BANDS:
            working_set_target = gpu_capacity_blocks * numerator // denominator
            builder_target = working_set_target - foreground_blocks
            if builder_target <= 0:
                reasons.append(
                    f"length={length} band={band} builder_target_blocks={builder_target} is not positive"
                )
            cells.append(
                {
                    "length": length,
                    "band": band,
                    "m_numerator": numerator,
                    "m_denominator": denominator,
                    "working_set_target_blocks": working_set_target,
                    "foreground_full_prefix_blocks": foreground_blocks,
                    "builder_target_blocks": builder_target,
                }
            )

    required_cpu_bytes = math.ceil(3 * gpu_capacity_blocks * block_bytes / 2)
    offloading_gib = math.ceil(required_cpu_bytes / (1 << 30))
    configured_cpu_bytes = offloading_gib * (1 << 30)
    if host_available_bytes < configured_cpu_bytes:
        reasons.append(
            "host_available_bytes={} is below configured S1 CPU tier bytes={}".format(
                host_available_bytes, configured_cpu_bytes
            )
        )
    return {
        "schema_version": 1,
        "status": "valid" if not reasons else "invalid_configuration",
        "reasons": reasons,
        "gpu_capacity_blocks": gpu_capacity_blocks,
        "block_size": block_size,
        "block_bytes": block_bytes,
        "gpu_kv_capacity_bytes": gpu_capacity_blocks * block_bytes,
        "host_available_bytes": host_available_bytes,
        "s1_required_cpu_bytes": required_cpu_bytes,
        "s1_kv_offloading_size_gib": offloading_gib,
        "s1_configured_cpu_bytes": configured_cpu_bytes,
        "cells": cells,
        "schedule_sha256": schedule_sha256(registered_schedule()),
    }


def write_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    """Atomically publish exactly one immutable comparative evidence bundle."""
    if set(files) != BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the seven A0.2 files")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".a02-stock-", dir=destination.parent))
    try:
        for name, value in files.items():
            (temporary / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if {path.name for path in temporary.iterdir()} != BUNDLE_FILES:
            raise ValueError("temporary A0.2 bundle is incomplete")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
