#!/usr/bin/env python3
"""Prepare one measured A0.2 foreground fixture without starting vLLM.

The builder changes only the system message by appending fixed archival records.
It measures the *whole* chat-template token sequence for every candidate and
accepts the closest reachable prompt length in the pre-registered window.  It
does not infer token length from character length or from the number of records.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from qualification import TARGET_FULL_PREFIX_TOKENS, initial_prompt_center, initial_prompt_window


FIXTURE = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/a0.1-fixture.json"
ARCHIVE_PREFIX = (
    "\n\n<archival-context>\n"
    "This archive is background only. Follow the user request and tool schema.\n"
)
ARCHIVE_SUFFIX = "</archival-context>"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, choices=TARGET_FULL_PREFIX_TOKENS, required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def archive_record(index: int) -> str:
    """A deterministic record whose leading/trailing newlines isolate BPE joins."""
    return "record={:05d}; class=archived; state=neutral;\n".format(index)


def _system_message_index(messages: Sequence[Mapping[str, Any]]) -> int:
    for index, message in enumerate(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            return index
    raise ValueError("fixture must contain a string-valued system message")


def _candidate_messages(
    base_messages: Sequence[Mapping[str, Any]], system_index: int, record_count: int
) -> list[dict[str, Any]]:
    messages = copy.deepcopy(list(base_messages))
    archive = "".join(archive_record(index) for index in range(record_count))
    messages[system_index]["content"] += ARCHIVE_PREFIX + archive + ARCHIVE_SUFFIX
    return messages


def build_fixture(
    base_fixture: Mapping[str, Any],
    target_full_prefix_tokens: int,
    *,
    render_ids: Callable[[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]], Sequence[int]],
) -> dict[str, Any]:
    """Return the closest measured fixture in the accepted full-block window.

    Records are appended one at a time and each candidate is measured through the
    caller-provided full-template tokenizer.  The chosen candidate is ordered by
    distance to the center, then by fewer records; this makes selection stable.
    """
    if target_full_prefix_tokens not in TARGET_FULL_PREFIX_TOKENS:
        raise ValueError("unsupported target_full_prefix_tokens: {}".format(target_full_prefix_tokens))

    initial_messages = base_fixture.get("initial_messages")
    tools = base_fixture.get("tools")
    if not isinstance(initial_messages, list) or not isinstance(tools, list):
        raise ValueError("fixture must contain initial_messages and tools lists")
    system_index = _system_message_index(initial_messages)
    low, high = initial_prompt_window(target_full_prefix_tokens)
    center = initial_prompt_center(target_full_prefix_tokens)
    candidates: list[tuple[int, int, list[dict[str, Any]]]] = []

    # The record format has a newline before every record.  Stop only after the
    # measured sequence has crossed the upper bound; if it never reaches the
    # window, the caller gets an explicit failure rather than a fabricated anchor.
    for record_count in range(target_full_prefix_tokens + 1):
        messages = _candidate_messages(initial_messages, system_index, record_count)
        prompt_tokens = len(render_ids(messages, tools))
        if low <= prompt_tokens <= high:
            candidates.append((prompt_tokens, record_count, messages))
        elif prompt_tokens > high:
            break

    if not candidates:
        raise ValueError(
            "no measured fixture reaches target {} prompt window [{}, {}]".format(
                target_full_prefix_tokens, low, high
            )
        )

    prompt_tokens, record_count, messages = min(
        candidates,
        key=lambda candidate: (
            abs(candidate[0] - center),
            candidate[1],
            candidate[0],
        ),
    )
    fixture = copy.deepcopy(dict(base_fixture))
    fixture["initial_messages"] = messages
    fixture["qualification"] = {
        "target_full_prefix_tokens": target_full_prefix_tokens,
        "accepted_r0_prompt_window": [low, high],
        "prepared_r0_prompt_tokens": prompt_tokens,
        "archive_record_count": record_count,
        "baseline_lcp_minus_r0_prompt": 21,
    }
    return fixture


def write_fixture(destination: Path, fixture: Mapping[str, Any]) -> None:
    if destination.exists():
        raise FileExistsError("refusing to overwrite fixture: {}".format(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(fixture, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _load_a01r_runner() -> Any:
    path = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual/run_task0.py"
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("a01r_fixture_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen A0.1R engine helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_ids_for_local_snapshot() -> Callable[[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]], Sequence[int]]:
    # These heavyweight imports are intentionally local: CPU tests must not need
    # a vLLM checkout or the model snapshot merely to exercise selection logic.
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    a01r = _load_a01r_runner()
    model_snapshot = a01r._local_model_snapshot(snapshot_download)
    tokenizer = AutoTokenizer.from_pretrained(model_snapshot, local_files_only=True)

    def render_ids(messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]) -> Sequence[int]:
        return a01r._render_ids(tokenizer, messages, tools)

    return render_ids


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    base_fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture = build_fixture(
        base_fixture,
        args.target,
        render_ids=_render_ids_for_local_snapshot(),
    )
    write_fixture(Path(args.output), fixture)
    print(
        json.dumps(
            {
                "target": args.target,
                "accepted_r0_prompt_window": fixture["qualification"]["accepted_r0_prompt_window"],
                "prepared_r0_prompt_tokens": fixture["qualification"]["prepared_r0_prompt_tokens"],
                "archive_record_count": fixture["qualification"]["archive_record_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
