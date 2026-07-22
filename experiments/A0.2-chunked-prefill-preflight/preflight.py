from __future__ import annotations

"""Pure verdict and artifact helpers for the chunked-prefill admission gate."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping


BLOCK_SIZE = 16
EXPECTED_CACHED_TOKENS = 192
EXPECTED_LCP = 199
BUNDLE_FILES = {
    "manifest.json",
    "r0.json",
    "r1.json",
    "accounting.json",
    "verdict.json",
}


@dataclass(frozen=True)
class PreflightVerdict:
    status: str
    reason: str
    expected_cached_tokens: int


def _valid_counter(value: int | None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def decide_preflight(
    *,
    r0_cached_tokens: int | None,
    r1_cached_tokens: int | None,
    r0_prompt_tokens: int | None = None,
    r1_prompt_tokens: int | None = None,
    lcp: int,
    semantic_span_equal: bool,
    block_size: int,
) -> PreflightVerdict:
    """Classify the new scheduler pin without reinterpreting a changed oracle."""
    if (
        not _valid_counter(r0_cached_tokens)
        or not _valid_counter(r1_cached_tokens)
        or (r0_prompt_tokens is not None and r0_cached_tokens > r0_prompt_tokens)
        or (r1_prompt_tokens is not None and r1_cached_tokens > r1_prompt_tokens)
        or block_size != BLOCK_SIZE
    ):
        status, reason = "invalid_run", "missing or malformed accounting/configuration"
    elif r0_cached_tokens != 0:
        status, reason = "invalid_run", "fresh-engine R0 was not cold"
    elif not semantic_span_equal:
        status, reason = "semantic_stop", "canonical semantic/token anchor drifted"
    elif lcp != EXPECTED_LCP:
        status, reason = "invalid_run", "LCP drifted from the registered anchor"
    elif r1_cached_tokens != EXPECTED_CACHED_TOKENS:
        status, reason = (
            "accounting_contract_change",
            "supported scheduler pin changed the registered cached-token oracle",
        )
    else:
        status, reason = (
            "admission_pass",
            "supported scheduler pin preserved the registered cached-token oracle",
        )
    return PreflightVerdict(
        status=status,
        reason=reason,
        expected_cached_tokens=EXPECTED_CACHED_TOKENS,
    )


def write_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    """Atomically publish exactly one immutable preflight evidence bundle."""
    if set(files) != BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the five preflight files")
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
        if {path.name for path in temporary.iterdir()} != BUNDLE_FILES:
            raise ValueError("temporary preflight bundle is incomplete")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
