from __future__ import annotations

"""Pure evidence and verdict helpers for A0.1R Task-0.

This module deliberately has no vLLM import. The runner passes through the
engine-owned token IDs and accounting fields without reconstructing them.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence

from toolgap_kv.a01 import Span, full_block_ceiling, lcp_length


TASK0_BUNDLE_FILES = {
    "manifest.json",
    "r0.json",
    "r1.json",
    "accounting.json",
    "verdict.json",
}


@dataclass(frozen=True)
class Task0Anchor:
    """Frozen A0.1 quantities that a Task-0 pair must reproduce."""

    r0_span: tuple[int, int]
    r1_span: tuple[int, int]
    lcp: int
    block_size: int
    eligible_full_prefix_tokens: int
    eligible_prefix_sha256: str


A01_TASK0_ANCHOR = Task0Anchor(
    r0_span=(178, 198),
    r1_span=(178, 198),
    lcp=199,
    block_size=16,
    eligible_full_prefix_tokens=192,
    eligible_prefix_sha256="0a93d9508f145bddcc4b67dfb11e73ac72bc11509f04c9d262254787562fe853",
)


@dataclass(frozen=True)
class Task0Verdict:
    status: str
    reason: str
    lcp: int
    eligible_full_prefix_tokens: int
    eligible_prefix_sha256: str
    semantic_span_equal: bool
    residual_shared_tokens: int
    semantic_tail_not_in_full_prefix: int
    r0_cached_tokens: int | None
    r1_cached_tokens: int | None
    recomputed_prompt_tokens: int | None


def _counter_is_valid(value: int | None, prompt_length: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= prompt_length
    )


def _prefix_sha256(token_ids: Sequence[int]) -> str:
    return hashlib.sha256(
        json.dumps(list(token_ids), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def decide_task0(
    *,
    r0_ids: Sequence[int],
    r1_ids: Sequence[int],
    r0_span: Span,
    r1_span: Span,
    block_size: int,
    r0_cached_tokens: int | None,
    r1_cached_tokens: int | None,
    evidence_valid: bool,
    expected_anchor: Task0Anchor,
) -> Task0Verdict:
    """Classify one exact R0/R1 pair before any pressure experiment.

    Classification order is intentional: malformed accounting is invalid before
    semantic interpretation; semantic loss is then a stop; frozen-anchor drift
    is invalid; only then may stock APC materialization be judged.
    """
    lcp = lcp_length(r0_ids, r1_ids)
    eligible = full_block_ceiling(lcp, block_size)
    eligible_prefix_sha256 = _prefix_sha256(r1_ids[:eligible])
    spans_valid = r0_span.end <= len(r0_ids) and r1_span.end <= len(r1_ids)
    semantic_equal = spans_valid and (
        list(r0_ids[r0_span.start : r0_span.end])
        == list(r1_ids[r1_span.start : r1_span.end])
    )
    counters_valid = _counter_is_valid(
        r0_cached_tokens, len(r0_ids)
    ) and _counter_is_valid(r1_cached_tokens, len(r1_ids))
    recomputed = (
        len(r1_ids) - r1_cached_tokens
        if _counter_is_valid(r1_cached_tokens, len(r1_ids))
        else None
    )

    if not evidence_valid or not counters_valid or not spans_valid:
        status, reason = "invalid_run", "missing or malformed request accounting"
    elif r0_cached_tokens != 0:
        status, reason = "invalid_run", "fresh-engine R0 was not cold"
    elif r1_cached_tokens % block_size != 0 or r1_cached_tokens > eligible:
        status, reason = (
            "invalid_run",
            "R1 accounting contradicts the full-block LCP oracle",
        )
    elif not semantic_equal or lcp < r1_span.end:
        status, reason = "semantic_stop", "canonical semantic prefix is not preserved"
    elif (
        (r0_span.start, r0_span.end) != expected_anchor.r0_span
        or (r1_span.start, r1_span.end) != expected_anchor.r1_span
        or lcp != expected_anchor.lcp
        or block_size != expected_anchor.block_size
        or eligible != expected_anchor.eligible_full_prefix_tokens
        or eligible_prefix_sha256 != expected_anchor.eligible_prefix_sha256
    ):
        status, reason = "invalid_run", "pair drifted from the registered A0.1 anchor"
    elif eligible == 0:
        status, reason = "stock_apc_unavailable", "no eligible full prefix block exists"
    elif r1_cached_tokens < eligible:
        status, reason = (
            "stock_apc_unavailable",
            "stock APC did not materialize the eligible prefix",
        )
    else:
        status, reason = (
            "admission_pass",
            "stock APC materialized the eligible full prefix",
        )

    return Task0Verdict(
        status=status,
        reason=reason,
        lcp=lcp,
        eligible_full_prefix_tokens=eligible,
        eligible_prefix_sha256=eligible_prefix_sha256,
        semantic_span_equal=semantic_equal,
        residual_shared_tokens=lcp - eligible,
        semantic_tail_not_in_full_prefix=max(0, r1_span.end - eligible),
        r0_cached_tokens=r0_cached_tokens,
        r1_cached_tokens=r1_cached_tokens,
        recomputed_prompt_tokens=recomputed,
    )


def write_task0_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    """Atomically publish exactly one immutable five-file Task-0 bundle."""
    if set(files) != TASK0_BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the five Task-0 files")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".a01r-task0-", dir=str(destination.parent))
    )
    try:
        for name, value in files.items():
            (temporary / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if {path.name for path in temporary.iterdir()} != TASK0_BUNDLE_FILES:
            raise ValueError("temporary Task-0 bundle is incomplete")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
