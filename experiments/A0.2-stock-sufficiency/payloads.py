"""Deterministic block-exact background payload construction for A0.2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Sequence


@dataclass(frozen=True)
class Payload:
    index: int
    role: str
    blocks: int
    prompt_token_ids: tuple[int, ...]
    first_block_sha256: str
    prompt_sha256: str


def _ids_sha256(ids: Sequence[int]) -> str:
    raw = json.dumps(list(ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _unique_first_block(
    *,
    index: int,
    block_size: int,
    nonce: str,
    usable_token_ids: Sequence[int],
    forbidden: set[tuple[int, ...]],
) -> tuple[int, ...]:
    counter = 0
    while True:
        digest = hashlib.sha512(f"{nonce}:{index}:{counter}".encode("utf-8")).digest()
        block = tuple(
            usable_token_ids[digest[position % len(digest)] % len(usable_token_ids)]
            for position in range(block_size)
        )
        if block not in forbidden:
            return block
        counter += 1


def _block_counts(total_blocks: int, payload_block_cap: int, active_probe_count: int) -> list[tuple[str, int]]:
    remaining = total_blocks
    counts: list[tuple[str, int]] = []
    while remaining - payload_block_cap >= active_probe_count:
        counts.append(("builder", payload_block_cap))
        remaining -= payload_block_cap
    base, extra = divmod(remaining, active_probe_count)
    if base <= 0:
        raise ValueError("total_blocks must leave at least one block per active probe")
    counts.extend(
        ("active_probe", base + (1 if index < extra else 0))
        for index in range(active_probe_count)
    )
    return counts


def build_payload_plan(
    *,
    total_blocks: int,
    block_size: int,
    nonce: str,
    usable_token_ids: Sequence[int],
    foreground_first_block: Sequence[int],
    payload_block_cap: int,
    active_probe_count: int,
) -> tuple[Payload, ...]:
    """Build exact W-background demand with unique first complete blocks."""
    if any(type(value) is not int or value <= 0 for value in (total_blocks, block_size, payload_block_cap, active_probe_count)):
        raise ValueError("block counts and sizes must be positive integers")
    if len(foreground_first_block) != block_size:
        raise ValueError("foreground_first_block must contain exactly block_size tokens")
    if len(usable_token_ids) < 2 or any(type(token) is not int or token < 0 for token in usable_token_ids):
        raise ValueError("usable_token_ids must contain non-negative integer token IDs")
    if len(set(usable_token_ids)) != len(usable_token_ids):
        raise ValueError("usable_token_ids must be unique")

    forbidden = {tuple(foreground_first_block)}
    filler = usable_token_ids[0]
    payloads: list[Payload] = []
    for index, (role, blocks) in enumerate(
        _block_counts(total_blocks, payload_block_cap, active_probe_count)
    ):
        first_block = _unique_first_block(
            index=index,
            block_size=block_size,
            nonce=nonce,
            usable_token_ids=usable_token_ids,
            forbidden=forbidden,
        )
        forbidden.add(first_block)
        prompt_ids = first_block + (filler,) * (blocks * block_size - block_size)
        payloads.append(
            Payload(
                index=index,
                role=role,
                blocks=blocks,
                prompt_token_ids=prompt_ids,
                first_block_sha256=_ids_sha256(first_block),
                prompt_sha256=_ids_sha256(prompt_ids),
            )
        )
    return tuple(payloads)


def payload_plan_sha256(plan: Sequence[Payload]) -> str:
    raw = json.dumps(
        [asdict(item) for item in plan],
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
