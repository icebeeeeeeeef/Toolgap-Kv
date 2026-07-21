#!/usr/bin/env python3
"""Run Gate A0.1 against one pinned in-process vLLM installation.

This is deliberately a one-off harness: five fresh workers establish an R0
anchor; only worker five is allowed to parse and submit R1 after the parent
confirms the five raw R0 sequences are identical.
"""

import argparse
import hashlib
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from toolgap_kv import a01 as a01_module
from toolgap_kv.a01 import (
    Span,
    decide,
    locate_span,
    message_region_from_prefixes,
    write_bundle,
)


VLLM_VERSION = "0.25.1"
VLLM_COMMIT = "752a3a504485790a2e8491cacbb35c137339ad34"
TOOL_ID_HELPER = "vllm.entrypoints.chat_utils.make_tool_call_id"
SPAN_ADAPTER_VERSION = "full-text-fast-tokenizer-offset-overlap-v1"
TOOL_PARSER = "Hermes2ProToolParser"


def _as_ids(value: Any) -> List[int]:
    if isinstance(value, Mapping):
        value = value.get("input_ids")
    if value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, (list, tuple)):
        raise ValueError("tokenizer did not return a token-ID sequence")
    return [int(token_id) for token_id in value]


def _as_offsets(value: Any) -> List[Tuple[int, int]]:
    if isinstance(value, Mapping):
        value = value.get("offset_mapping")
    if value and isinstance(value[0], list) and value[0] and isinstance(value[0][0], (list, tuple)):
        value = value[0]
    if not isinstance(value, (list, tuple)):
        raise ValueError("fast tokenizer did not return offset_mapping")
    return [(int(item[0]), int(item[1])) for item in value]


def _render_ids(tokenizer: Any, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]) -> List[int]:
    rendered = tokenizer.apply_chat_template(
        list(messages), tools=list(tools), tokenize=True, add_generation_prompt=True
    )
    return _as_ids(rendered)


def _render_text(tokenizer: Any, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]) -> str:
    rendered = tokenizer.apply_chat_template(
        list(messages), tools=list(tools), tokenize=False, add_generation_prompt=True
    )
    if not isinstance(rendered, str):
        raise ValueError("chat template did not return text")
    return rendered


def _full_encoding(tokenizer: Any, rendered: str) -> Tuple[List[int], List[Tuple[int, int]]]:
    encoded = tokenizer(
        rendered, add_special_tokens=False, return_offsets_mapping=True
    )
    return _as_ids(encoded), _as_offsets(encoded)


def _normal_tool_call(tool_call: Any) -> Dict[str, Any]:
    function = tool_call.function
    return {
        "name": str(function.name),
        "arguments": json.loads(str(function.arguments)),
    }


def _parse_one_tool_call(parser: Any, text: str) -> Dict[str, Any]:
    # The fixed v0.25.1 Hermes non-streaming parser does not inspect request.
    parsed = parser.extract_tool_calls(text, None)
    if not parsed.tools_called or len(parsed.tool_calls) != 1:
        raise ValueError("Hermes parser did not return exactly one tool call")
    return _normal_tool_call(parsed.tool_calls[0])


def _gpu_provenance() -> Dict[str, Any]:
    import torch

    driver = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "name": torch.cuda.get_device_name(0),
        "cuda": torch.version.cuda,
        "driver": driver.stdout.strip() if driver.returncode == 0 else "unavailable",
    }


def _pinned_vllm_commit(vllm_module: Any) -> Tuple[str, str]:
    """Prove that the imported editable vLLM checkout is the frozen source pin."""
    module_file = getattr(vllm_module, "__file__", None)
    if not module_file:
        raise RuntimeError("vLLM module does not expose an import path")
    source_root = Path(module_file).resolve().parents[1]
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or len(commit) != 40:
        raise RuntimeError("vLLM import is not a readable source checkout")
    if commit != VLLM_COMMIT:
        raise RuntimeError("expected vLLM commit {}, got {}".format(VLLM_COMMIT, commit))
    return commit, str(source_root)


def _span_adapter_sha256() -> str:
    return hashlib.sha256(Path(a01_module.__file__).read_bytes()).hexdigest()


def _span_for_full_render(
    tokenizer: Any,
    rendered: str,
    actual_ids: Sequence[int],
    open_marker: str,
    close_marker: str,
    *,
    search_start: int = 0,
    search_end: int = None,
) -> Span:
    local_ids, offsets = _full_encoding(tokenizer, rendered)
    if local_ids != list(actual_ids):
        raise ValueError("full local tokenization does not equal engine token IDs")
    return locate_span(
        rendered,
        open_marker,
        close_marker,
        offsets,
        search_start=search_start,
        search_end=search_end,
    )


def _worker(ordinal: int, configuration: Mapping[str, Any], connection: Any) -> None:
    captured_r0 = None
    try:
        import vllm
        from vllm import LLM, SamplingParams

        if vllm.__version__ != VLLM_VERSION:
            raise RuntimeError("expected vLLM {}, got {}".format(VLLM_VERSION, vllm.__version__))
        vllm_commit, vllm_source_root = _pinned_vllm_commit(vllm)
        fixture = configuration["fixture"]
        llm = LLM(
            model=configuration["model"],
            revision=configuration["model_revision"],
            tokenizer_revision=configuration["tokenizer_revision"],
            tensor_parallel_size=1,
            enable_chunked_prefill=configuration["chunked_prefill"] == "enabled",
            spec_method=None,
        )
        sampling = SamplingParams(temperature=0, max_tokens=configuration["max_tokens"])
        r0_output = llm.chat(
            fixture["initial_messages"],
            sampling_params=sampling,
            tools=fixture["tools"],
            use_tqdm=False,
        )[0]
        if len(r0_output.outputs) != 1:
            raise ValueError("R0 did not contain exactly one completion")
        tokenizer = llm.get_tokenizer()
        prompt_ids = list(r0_output.prompt_token_ids)
        completion = r0_output.outputs[0]
        completion_ids = list(completion.token_ids)
        completion_text = str(completion.text)
        captured_r0 = {
            "prompt_ids": prompt_ids,
            "completion_ids": completion_ids,
            "r0_ids": prompt_ids + completion_ids,
            "completion_text": completion_text,
        }
        local_r0_ids = _render_ids(tokenizer, fixture["initial_messages"], fixture["tools"])
        payload = {
            "kind": "r0",
            "ordinal": ordinal,
            **captured_r0,
            "local_prompt_ids": local_r0_ids,
            "local_prompt_equal": local_r0_ids == prompt_ids,
            "vllm_version": vllm.__version__,
            "vllm_commit": vllm_commit,
            "vllm_source_root": vllm_source_root,
        }
        connection.send(payload)
        if ordinal != 5:
            return

        command = connection.recv()
        if command.get("command") != "resume":
            return
        from vllm.entrypoints.chat_utils import make_tool_call_id
        from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser

        parser = Hermes2ProToolParser(tokenizer, tools=fixture["tools"])
        r0_tool = _parse_one_tool_call(parser, completion_text)
        tool_call_id = make_tool_call_id()
        assistant = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": r0_tool["name"],
                        "arguments": json.dumps(r0_tool["arguments"], ensure_ascii=False, separators=(",", ":")),
                    },
                }
            ],
        }
        r1_messages = list(fixture["initial_messages"]) + [
            assistant,
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(fixture["tool_result"], ensure_ascii=False, separators=(",", ":")),
            },
            {"role": "user", "content": fixture["resume_prompt"]},
        ]
        r1_output = llm.chat(
            r1_messages,
            sampling_params=SamplingParams(temperature=0, max_tokens=1),
            tools=fixture["tools"],
            use_tqdm=False,
        )[0]
        r1_ids = list(r1_output.prompt_token_ids)
        r1_rendered = _render_text(tokenizer, r1_messages, fixture["tools"])
        initial_rendered = tokenizer.apply_chat_template(
            list(fixture["initial_messages"]),
            tools=list(fixture["tools"]),
            tokenize=False,
            add_generation_prompt=False,
        )
        through_assistant_rendered = tokenizer.apply_chat_template(
            r1_messages[: len(fixture["initial_messages"]) + 1],
            tools=list(fixture["tools"]),
            tokenize=False,
            add_generation_prompt=False,
        )
        assistant_region_start, assistant_region_end = message_region_from_prefixes(
            r1_rendered,
            str(initial_rendered),
            str(through_assistant_rendered),
        )
        open_marker = str(parser.tool_call_start_token)
        close_marker = str(parser.tool_call_end_token)
        r1_span = _span_for_full_render(
            tokenizer,
            r1_rendered,
            r1_ids,
            open_marker,
            close_marker,
            search_start=assistant_region_start,
            search_end=assistant_region_end,
        )
        r0_text = tokenizer.decode(
            completion_ids,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        r0_completion_span = _span_for_full_render(
            tokenizer, r0_text, completion_ids, open_marker, close_marker
        )
        r0_span = Span(
            start=len(prompt_ids) + r0_completion_span.start,
            end=len(prompt_ids) + r0_completion_span.end,
            left_boundary_expansion=r0_completion_span.left_boundary_expansion,
            right_boundary_expansion=r0_completion_span.right_boundary_expansion,
        )
        r1_envelope_start = r1_rendered.index(
            open_marker, assistant_region_start, assistant_region_end
        )
        r1_envelope_end = (
            r1_rendered.index(close_marker, r1_envelope_start, assistant_region_end)
            + len(close_marker)
        )
        r1_tool = _parse_one_tool_call(parser, r1_rendered[r1_envelope_start:r1_envelope_end])
        if r0_tool != r1_tool:
            raise ValueError("R0 and R1 parser structures differ")
        template = str(getattr(tokenizer, "chat_template", ""))
        if not template:
            raise ValueError("tokenizer did not expose the active chat template")
        block_size = int(llm.llm_engine.vllm_config.cache_config.block_size)
        connection.send(
            {
                "kind": "r1",
                "r1_ids": r1_ids,
                "r1_messages": r1_messages,
                "r1_rendered": r1_rendered,
                "r0_span": r0_span.__dict__,
                "r1_span": r1_span.__dict__,
                "r0_tool": r0_tool,
                "r1_tool": r1_tool,
                "tool_call_id": tool_call_id,
                "template": template,
                "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
                "open_marker": open_marker,
                "close_marker": close_marker,
                "block_size": block_size,
                "gpu": _gpu_provenance(),
                "vllm_version": vllm.__version__,
                "vllm_commit": vllm_commit,
                "vllm_source_root": vllm_source_root,
            }
        )
    except Exception as error:
        connection.send(
            {
                "kind": "invalid_run" if captured_r0 is not None else "infrastructure_failure",
                "ordinal": ordinal,
                "reason": str(error),
                "traceback": traceback.format_exc(),
                "captured_r0": captured_r0,
            }
        )
    finally:
        connection.close()


def _receive_r0(
    context: Any, ordinal: int, configuration: Mapping[str, Any], timeout_seconds: int
) -> Tuple[Any, Any, Mapping[str, Any]]:
    for attempt in (1, 2):
        parent, child = context.Pipe()
        process = context.Process(target=_worker, args=(ordinal, configuration, child))
        process.start()
        child.close()
        if parent.poll(timeout_seconds):
            message = parent.recv()
        else:
            process.terminate()
            process.join()
            message = {"kind": "infrastructure_failure", "reason": "worker timed out"}
        if message.get("kind") != "infrastructure_failure" or attempt == 2:
            return process, parent, message
        process.join()
    raise AssertionError("unreachable")


def _base_bundle(configuration: Mapping[str, Any], status: str, reason: str) -> Dict[str, Any]:
    manifest = {
        "experiment": "A0.1-token-roundtrip",
        "status": status,
        "reason": reason,
        "expected_vllm_version": VLLM_VERSION,
        "expected_vllm_commit": VLLM_COMMIT,
        "model": configuration["model"],
        "model_revision": configuration["model_revision"],
        "tokenizer_revision": configuration["tokenizer_revision"],
        "fixture_sha256": configuration["fixture_sha256"],
        "tool_schema_sha256": configuration["tool_schema_sha256"],
        "chunked_prefill": configuration["chunked_prefill"],
        "tensor_parallel_size": 1,
        "speculative_decoding": False,
        "temperature": 0,
        "tool_call_id_helper": TOOL_ID_HELPER,
        "tool_parser": TOOL_PARSER,
    }
    return {
        "manifest.json": manifest,
        "span_adapter.json": {},
        "template.jinja": "",
        "r0.json": {},
        "r1.json": {},
        "verdict.json": {"status": status, "reason": reason},
    }


def _finish_process(process: Any) -> None:
    process.join(timeout=10)
    if process.is_alive():
        process.terminate()
        process.join()


def run(configuration: Mapping[str, Any], destination: Path, timeout_seconds: int) -> str:
    context = multiprocessing.get_context("spawn")
    r0_messages = []
    fifth_process = None
    fifth_connection = None
    for ordinal in range(1, 6):
        process, connection, message = _receive_r0(context, ordinal, configuration, timeout_seconds)
        if message.get("kind") != "r0":
            bundle = _base_bundle(configuration, "environment_blocked" if message.get("kind") == "infrastructure_failure" else "invalid_run", message.get("reason", "R0 unavailable"))
            bundle["r0.json"] = {"preflight": r0_messages, "failure": message}
            write_bundle(destination, bundle)
            _finish_process(process)
            return bundle["verdict.json"]["status"]
        r0_messages.append(message)
        if ordinal == 5:
            fifth_process, fifth_connection = process, connection
        else:
            _finish_process(process)
    raw_r0 = [message["r0_ids"] for message in r0_messages]
    if raw_r0.count(raw_r0[0]) != 5 or not r0_messages[0]["local_prompt_equal"]:
        bundle = _base_bundle(configuration, "invalid_run", "R0 preflight was not a stable local-rendered engine anchor")
        bundle["r0.json"] = {"preflight": r0_messages}
        write_bundle(destination, bundle)
        fifth_connection.send({"command": "stop"})
        _finish_process(fifth_process)
        return "invalid_run"
    fifth_connection.send({"command": "resume"})
    if not fifth_connection.poll(timeout_seconds):
        _finish_process(fifth_process)
        bundle = _base_bundle(configuration, "invalid_run", "fifth worker did not complete parser/R1")
        bundle["r0.json"] = {"preflight": r0_messages}
        write_bundle(destination, bundle)
        return "invalid_run"
    r1_message = fifth_connection.recv()
    _finish_process(fifth_process)
    if r1_message.get("kind") != "r1":
        bundle = _base_bundle(configuration, "invalid_run", r1_message.get("reason", "parser/R1 unavailable"))
        bundle["r0.json"] = {"preflight": r0_messages}
        bundle["r1.json"] = {"failure": r1_message}
        write_bundle(destination, bundle)
        return "invalid_run"
    r0_span = Span(**r1_message["r0_span"])
    r1_span = Span(**r1_message["r1_span"])
    verdict = decide(
        r0_ids=r0_messages[4]["r0_ids"],
        r1_ids=r1_message["r1_ids"],
        r0_span=r0_span,
        r1_span=r1_span,
        block_size=r1_message["block_size"],
        evidence_valid=True,
    )
    bundle = _base_bundle(configuration, verdict.status, "A0.1 decision table")
    bundle["manifest.json"].update(
        {
            "block_size": r1_message["block_size"],
            "vllm_version": r1_message["vllm_version"],
            "vllm_commit": r1_message["vllm_commit"],
            "vllm_source_root": r1_message["vllm_source_root"],
            "tool_call_id": r1_message["tool_call_id"],
            "template_sha256": r1_message["template_sha256"],
            "gpu": r1_message["gpu"],
            "argv": configuration["argv"],
        }
    )
    bundle["span_adapter.json"] = {
        "open_marker": r1_message["open_marker"],
        "close_marker": r1_message["close_marker"],
        "template_sha256": r1_message["template_sha256"],
        "version": SPAN_ADAPTER_VERSION,
        "adapter_sha256": _span_adapter_sha256(),
        "algorithm": SPAN_ADAPTER_VERSION,
        "non_nesting": "exactly_one_open_then_one_close",
    }
    bundle["template.jinja"] = r1_message["template"]
    bundle["r0.json"] = {"preflight": r0_messages, "assistant_span": r1_message["r0_span"], "parser_tool": r1_message["r0_tool"]}
    bundle["r1.json"] = {"messages": r1_message["r1_messages"], "prompt_token_ids": r1_message["r1_ids"], "rendered": r1_message["r1_rendered"], "assistant_span": r1_message["r1_span"], "parser_tool": r1_message["r1_tool"]}
    bundle["verdict.json"] = {
        "status": verdict.status,
        "lcp": verdict.lcp,
        "reusable_full_block_ceiling": verdict.reusable_full_block_ceiling,
        "mismatch_region": verdict.mismatch_region,
        "semantic_span_equal": verdict.semantic_span_equal,
        "a_end_mod_block_size": r1_span.end % r1_message["block_size"],
        "coverage_slack": verdict.reusable_full_block_ceiling - r1_span.end,
    }
    write_bundle(destination, bundle)
    return verdict.status


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--model-revision", required=True, help="resolved immutable Hugging Face commit SHA")
    parser.add_argument("--tokenizer-revision", help="defaults to --model-revision")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--raw-root", type=Path, default=Path("experiments/0001-mechanism-feasibility/raw/a0.1"))
    parser.add_argument("--chunked-prefill", choices=("enabled", "disabled"), required=True)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--worker-timeout-s", type=int, default=900)
    return parser.parse_args(argv)


def main(argv: Sequence[str] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_tokens <= 0 or args.worker_timeout_s <= 0:
        raise SystemExit("--max-tokens and --worker-timeout-s must be positive")
    if len(args.model_revision) != 40 or any(character not in "0123456789abcdef" for character in args.model_revision.lower()):
        raise SystemExit("--model-revision must be a 40-character commit SHA")
    fixture_path = Path("experiments/0001-mechanism-feasibility/a0.1-fixture.json")
    configuration = {
        "fixture": json.loads(fixture_path.read_text(encoding="utf-8")),
        "model": args.model,
        "model_revision": args.model_revision,
        "tokenizer_revision": args.tokenizer_revision or args.model_revision,
        "chunked_prefill": args.chunked_prefill,
        "max_tokens": args.max_tokens,
        "argv": list(sys.argv),
    }
    fixture_bytes = json.dumps(
        configuration["fixture"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    tool_bytes = json.dumps(
        configuration["fixture"]["tools"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    configuration["fixture_sha256"] = hashlib.sha256(fixture_bytes).hexdigest()
    configuration["tool_schema_sha256"] = hashlib.sha256(tool_bytes).hexdigest()
    status = run(configuration, args.raw_root / args.run_id, args.worker_timeout_s)
    print("A0.1 {}".format(status))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
