"""Pure A0.1 token-round-trip evidence helpers.

This module intentionally has no vLLM import. The runner supplies engine-owned
token arrays; these functions only classify and preserve that evidence.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence, Tuple


REQUIRED_BUNDLE_FILES = {
    "manifest.json",
    "span_adapter.json",
    "template.jinja",
    "r0.json",
    "r1.json",
    "verdict.json",
}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    left_boundary_expansion: bool = False
    right_boundary_expansion: bool = False

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span must be a non-empty half-open interval")


@dataclass(frozen=True)
class Verdict:
    status: str
    lcp: int
    reusable_full_block_ceiling: int
    mismatch_region: str
    semantic_span_equal: bool


def _require_token_ids(token_ids: Sequence[int], name: str) -> None:
    if any(isinstance(token_id, bool) or not isinstance(token_id, int) for token_id in token_ids):
        raise ValueError("{} must contain only integer token IDs".format(name))


def lcp_length(left: Sequence[int], right: Sequence[int]) -> int:
    """Return the raw-ID longest common prefix length."""
    _require_token_ids(left, "left")
    _require_token_ids(right, "right")
    for index, (left_id, right_id) in enumerate(zip(left, right)):
        if left_id != right_id:
            return index
    return min(len(left), len(right))


def full_block_ceiling(lcp: int, block_size: int) -> int:
    if isinstance(lcp, bool) or not isinstance(lcp, int) or lcp < 0:
        raise ValueError("lcp must be a non-negative integer")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size <= 0:
        raise ValueError("block_size must be positive")
    return block_size * (lcp // block_size)


def _unique_envelope(rendered: str, open_marker: str, close_marker: str) -> Tuple[int, int]:
    if not all(isinstance(value, str) and value for value in (rendered, open_marker, close_marker)):
        raise ValueError("rendered text and markers must be non-empty strings")
    open_positions = []
    start = 0
    while True:
        position = rendered.find(open_marker, start)
        if position < 0:
            break
        open_positions.append(position)
        start = position + len(open_marker)
    if len(open_positions) != 1:
        first_close = rendered.find(close_marker, open_positions[0] + len(open_marker)) if open_positions else -1
        if len(open_positions) > 1 and first_close > open_positions[1]:
            raise ValueError("tool-call envelope markers are nested")
        raise ValueError("tool-call envelope must have one unique open marker")
    close_start = open_positions[0] + len(open_marker)
    close_position = rendered.find(close_marker, close_start)
    if close_position < 0:
        raise ValueError("tool-call envelope must have one close marker")
    if rendered.find(close_marker, close_position + len(close_marker)) >= 0:
        raise ValueError("tool-call envelope must have one unique close marker")
    if rendered.find(open_marker, close_start) >= 0:
        raise ValueError("tool-call envelope markers are nested")
    return open_positions[0], close_position + len(close_marker)


def locate_span(
    rendered: str,
    open_marker: str,
    close_marker: str,
    offsets: Sequence[Tuple[int, int]],
) -> Span:
    """Map the unique wire envelope to whole-token coordinates.

    ``offsets`` must come from one full-text fast-tokenizer encoding, not from
    independently encoded string segments.
    """
    envelope_start, envelope_end = _unique_envelope(rendered, open_marker, close_marker)
    overlaps = []
    for index, offset in enumerate(offsets):
        if not isinstance(offset, tuple) or len(offset) != 2:
            raise ValueError("offset mappings must contain (start, end) pairs")
        start, end = offset
        if any(isinstance(value, bool) or not isinstance(value, int) for value in offset):
            raise ValueError("offset mappings must contain integer positions")
        if start < 0 or end < start or end > len(rendered):
            raise ValueError("offset mapping is outside rendered text")
        if start < envelope_end and end > envelope_start:
            overlaps.append((index, start, end))
    if not overlaps:
        raise ValueError("offset mapping does not cover tool-call envelope")
    first_index, first_start, _ = overlaps[0]
    last_index, _, last_end = overlaps[-1]
    return Span(
        start=first_index,
        end=last_index + 1,
        left_boundary_expansion=first_start < envelope_start,
        right_boundary_expansion=last_end > envelope_end,
    )


def classify_mismatch(lcp: int, r1_length: int, span: Span) -> str:
    if lcp < 0 or r1_length < 0:
        raise ValueError("LCP and R1 length must be non-negative")
    if lcp < span.start:
        return "before_assistant_semantic"
    if lcp < span.end:
        return "assistant_semantic"
    return "after_assistant_semantic_or_r0_exhausted"


def decide(
    *,
    r0_ids: Sequence[int],
    r1_ids: Sequence[int],
    r0_span: Span,
    r1_span: Span,
    block_size: int,
    evidence_valid: bool,
) -> Verdict:
    """Apply the A0.1 pass/stop/invalid decision table to raw token IDs."""
    _require_token_ids(r0_ids, "r0_ids")
    _require_token_ids(r1_ids, "r1_ids")
    if r0_span.end > len(r0_ids) or r1_span.end > len(r1_ids):
        raise ValueError("semantic span is outside its raw token sequence")
    lcp = lcp_length(r0_ids, r1_ids)
    ceiling = full_block_ceiling(lcp, block_size)
    mismatch_region = classify_mismatch(lcp, len(r1_ids), r1_span)
    semantic_span_equal = (
        list(r0_ids[r0_span.start : r0_span.end])
        == list(r1_ids[r1_span.start : r1_span.end])
    )
    if not evidence_valid:
        status = "invalid_run"
    elif not semantic_span_equal or ceiling < r1_span.end:
        status = "serialization_stop"
    else:
        status = "pass"
    return Verdict(
        status=status,
        lcp=lcp,
        reusable_full_block_ceiling=ceiling,
        mismatch_region=mismatch_region,
        semantic_span_equal=semantic_span_equal,
    )


def write_bundle(destination: Path, files: Mapping[str, Any]) -> None:
    """Atomically publish exactly the A0.1 six-file raw-evidence bundle."""
    if set(files) != REQUIRED_BUNDLE_FILES:
        raise ValueError("bundle must contain exactly the six required evidence files")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".a01-", dir=str(destination.parent)))
    try:
        for name, value in files.items():
            path = temporary / name
            if name.endswith(".json"):
                path.write_text(
                    json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            elif isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                raise ValueError("{} must be text".format(name))
        actual = {path.name for path in temporary.iterdir()}
        if actual != REQUIRED_BUNDLE_FILES:
            raise ValueError("temporary bundle is incomplete")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
