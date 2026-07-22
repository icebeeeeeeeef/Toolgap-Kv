"""Pure contracts for A0.2 foreground-length qualification.

This module deliberately does not import vLLM. Runners provide engine-owned
token IDs, spans, and accounting; this module only validates and preserves
that evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence

from toolgap_kv.a01 import Span, full_block_ceiling


TARGET_FULL_PREFIX_TOKENS = (2048, 8192, 16384)
BLOCK_SIZE = 16
BASELINE_LCP_MINUS_R0_PROMPT = 21
FULL_BLOCK_RESIDUAL_TOKENS = range(BLOCK_SIZE)
BUNDLE_FILES = {
    "manifest.json",
    "fixture.json",
    "r0-reproducibility.json",
    "r1.json",
    "accounting.json",
    "verdict.json",
}


@dataclass(frozen=True)
class LengthQualificationVerdict:
    status: str
    reason: str
    target_full_prefix_tokens: int
    observed_full_prefix_tokens: int | None


def _require_target(target_full_prefix_tokens: int) -> None:
    if target_full_prefix_tokens not in TARGET_FULL_PREFIX_TOKENS:
        raise ValueError("target must be one of {}".format(TARGET_FULL_PREFIX_TOKENS))


def initial_prompt_window(target_full_prefix_tokens: int) -> tuple[int, int]:
    """Return the pre-tool prompt interval that centers the known residual."""
    _require_target(target_full_prefix_tokens)
    low = target_full_prefix_tokens - BASELINE_LCP_MINUS_R0_PROMPT
    return low, low + BLOCK_SIZE - 1


def initial_prompt_center(target_full_prefix_tokens: int) -> int:
    low, high = initial_prompt_window(target_full_prefix_tokens)
    return (low + high + 1) // 2


def _valid_counter(value: int | None, prompt_length: int | None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and isinstance(prompt_length, int)
        and not isinstance(prompt_length, bool)
        and 0 <= value <= prompt_length
    )


def _valid_span(value: Span) -> bool:
    return isinstance(value, Span) and value.start >= 0 and value.end > value.start


def decide_qualification(
    *,
    r0_cached_tokens: int | None,
    r1_cached_tokens: int | None,
    r0_prompt_tokens: int | None,
    r1_prompt_tokens: int | None,
    r0_completion_id_sequences: Sequence[Sequence[int]],
    lcp: int,
    semantic_span_equal: bool,
    r0_span: Span,
    r1_span: Span,
    block_size: int,
    target_full_prefix_tokens: int,
    evidence_valid: bool,
) -> LengthQualificationVerdict:
    """Classify one five-R0 / one-R1 length qualification observation."""
    _require_target(target_full_prefix_tokens)
    try:
        observed_full = full_block_ceiling(lcp, block_size)
    except ValueError:
        return LengthQualificationVerdict(
            "invalid_run",
            "malformed LCP or block-size provenance",
            target_full_prefix_tokens,
            None,
        )

    if not evidence_valid or block_size != BLOCK_SIZE or not _valid_span(r0_span) or not _valid_span(r1_span):
        return LengthQualificationVerdict(
            "invalid_run",
            "malformed provenance or semantic span",
            target_full_prefix_tokens,
            observed_full,
        )
    if not _valid_counter(r0_cached_tokens, r0_prompt_tokens) or not _valid_counter(
        r1_cached_tokens, r1_prompt_tokens
    ):
        return LengthQualificationVerdict(
            "accounting_contract_change",
            "cached-token accounting is missing or malformed",
            target_full_prefix_tokens,
            observed_full,
        )
    if r0_cached_tokens != 0 or len(r0_completion_id_sequences) != 5:
        return LengthQualificationVerdict(
            "invalid_run",
            "R0 was not cold or did not have five isolated observations",
            target_full_prefix_tokens,
            observed_full,
        )
    if any(
        not isinstance(ids, Sequence)
        or any(type(token_id) is not int for token_id in ids)
        for ids in r0_completion_id_sequences
    ) or len({tuple(ids) for ids in r0_completion_id_sequences}) != 1:
        return LengthQualificationVerdict(
            "invalid_run",
            "R0 completion IDs were not reproducible",
            target_full_prefix_tokens,
            observed_full,
        )
    if r1_cached_tokens % block_size != 0 or r1_cached_tokens > observed_full:
        return LengthQualificationVerdict(
            "accounting_contract_change",
            "R1 accounting contradicts the full-block LCP oracle",
            target_full_prefix_tokens,
            observed_full,
        )
    if not semantic_span_equal or lcp < r1_span.end:
        return LengthQualificationVerdict(
            "semantic_stop",
            "tool-call semantic prefix drifted",
            target_full_prefix_tokens,
            observed_full,
        )
    if (
        observed_full != target_full_prefix_tokens
        or r1_cached_tokens != target_full_prefix_tokens
    ):
        return LengthQualificationVerdict(
            "fixture_qualification_stop",
            "fixture did not materialize the target full prefix",
            target_full_prefix_tokens,
            observed_full,
        )
    return LengthQualificationVerdict(
        "admission_pass",
        "target full prefix round-tripped and materialized",
        target_full_prefix_tokens,
        observed_full,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _compact_ids_sha256(token_ids: Sequence[int]) -> str:
    if any(type(token_id) is not int for token_id in token_ids):
        raise ValueError("token IDs must be integers")
    return hashlib.sha256(
        json.dumps(list(token_ids), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    """Atomically publish exactly one immutable qualification evidence bundle."""
    if set(files) != BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the required qualification files")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".a02-foreground-qualification-", dir=destination.parent)
    )
    try:
        for name, value in files.items():
            (temporary / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if {path.name for path in temporary.iterdir()} != BUNDLE_FILES:
            raise ValueError("temporary qualification bundle is incomplete")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _span_from_evidence(value: Any, name: str) -> list[int]:
    if isinstance(value, Mapping):
        start, end = value.get("start"), value.get("end")
    elif isinstance(value, list) and len(value) == 2:
        start, end = value
    else:
        raise ValueError("{} must be a mapping or [start, end] list".format(name))
    if any(type(item) is not int for item in (start, end)) or start < 0 or end <= start:
        raise ValueError("{} must be a non-empty integer interval".format(name))
    return [start, end]


def promoted_anchor_from_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the only tracked anchor representation from a passing raw bundle."""
    if set(bundle) != BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the required qualification files")
    verdict = bundle["verdict.json"]
    r1 = bundle["r1.json"]
    manifest = bundle["manifest.json"]
    if not isinstance(verdict, Mapping) or verdict.get("status") != "admission_pass":
        raise ValueError("only admission_pass evidence may be promoted")
    if not isinstance(r1, Mapping) or not isinstance(manifest, Mapping):
        raise ValueError("bundle has malformed R1 or manifest evidence")
    target = verdict.get("target_full_prefix_tokens")
    observed = verdict.get("observed_full_prefix_tokens")
    block_size = verdict.get("block_size")
    if (
        target not in TARGET_FULL_PREFIX_TOKENS
        or observed != target
        or block_size != BLOCK_SIZE
    ):
        raise ValueError("bundle verdict cannot promote an unregistered target")
    prompt_ids = r1.get("prompt_token_ids")
    if not isinstance(prompt_ids, Sequence) or len(prompt_ids) < target:
        raise ValueError("R1 prompt does not cover the eligible target prefix")
    return {
        "schema_version": 1,
        "target_full_prefix_tokens": target,
        "block_size": block_size,
        "r0_span": _span_from_evidence(verdict.get("r0_span"), "r0_span"),
        "r1_span": _span_from_evidence(verdict.get("r1_span"), "r1_span"),
        "lcp": verdict.get("lcp"),
        "eligible_prefix_sha256": _compact_ids_sha256(prompt_ids[:target]),
        "source_bundle_sha256": hashlib.sha256(_canonical_json_bytes(manifest)).hexdigest(),
    }
