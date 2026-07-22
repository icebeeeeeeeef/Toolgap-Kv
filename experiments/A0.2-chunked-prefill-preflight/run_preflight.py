#!/usr/bin/env python3
"""Run one supported-chunked-prefill admission preflight ordinal.

The historical A0.1R harness is deliberately left frozen. This runner reuses
its engine-truth extraction helpers, but records a new experiment and gives a
changed cached-token value its own ``accounting_contract_change`` verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Sequence, Tuple


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
A01R_DIR = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual"
A01R_RUNNER = A01R_DIR / "run_task0.py"
AUDIT = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/A0.2-chunked-prefill-configuration-audit.md"
RAW_ROOT = EXPERIMENT_DIR / "raw"
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from preflight import EXPECTED_CACHED_TOKENS, EXPECTED_LCP, PreflightVerdict, decide_preflight, write_bundle
from toolgap_kv.a01 import Span, lcp_length, message_region_from_prefixes


EXPECTED_SPAN = (178, 198)
EXPECTED_BLOCK_SIZE = 16
EXPECTED_PREFIX_SHA256 = "0a93d9508f145bddcc4b67dfb11e73ac72bc11509f04c9d262254787562fe853"


def _load_a01r_runner() -> Any:
    spec = importlib.util.spec_from_file_location("a01r_frozen_runner", A01R_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen A0.1R runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinal", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--attempt", type=int, default=1)
    return parser.parse_args(argv)


def destination_for(raw_root: Path, ordinal: int, attempt: int) -> Path:
    if attempt <= 0:
        raise ValueError("attempt must be positive")
    return raw_root / "preflight" / "preflight-o{:02d}-a{:02d}".format(ordinal, attempt)


def _engine_kwargs(model_snapshot: str) -> Dict[str, Any]:
    return {
        "model": model_snapshot,
        "tokenizer": model_snapshot,
        "tensor_parallel_size": 1,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "spec_method": None,
        "seed": 0,
        "disable_log_stats": False,
    }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tracked_inputs() -> Tuple[Dict[str, str], str]:
    paths = (
        EXPERIMENT_DIR / "run_preflight.py",
        EXPERIMENT_DIR / "preflight.py",
        AUDIT,
        A01R_DIR / "run_task0.py",
        A01R_DIR / "task0.py",
        REPOSITORY_ROOT / "src/toolgap_kv/a01.py",
        REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/a0.1-fixture.json",
        A01R_DIR / "a0.1-task0-prefix-anchor.json",
    )
    relative = tuple(str(path.relative_to(REPOSITORY_ROOT)) for path in paths)
    for path in relative:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        )
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *relative],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    project_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return ({path: _sha256_bytes(file.read_bytes()) for path, file in zip(relative, paths)}, project_head)


def _base_manifest(
    *,
    ordinal: int,
    attempt: int,
    project_head: str,
    input_hashes: Mapping[str, str],
    a01r: Any,
    fixture_hash: str,
    tools_hash: str,
    model_snapshot: str,
    vllm_distribution_version: str,
    vllm_commit: str,
    vllm_source_root: str,
    gpu: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "experiment": "A0.2-chunked-prefill-preflight",
        "task": "supported-scheduler-apc-admission",
        "execution_mode": "blocking-single-request-llm-chat",
        "ordinal": ordinal,
        "attempt": attempt,
        "argv": list(sys.argv),
        "project_head": project_head,
        "tracked_input_sha256": dict(input_hashes),
        "fixture": {"expected_sha256": a01r.FIXTURE_SHA256, "actual_sha256": fixture_hash},
        "tools": {"expected_sha256": a01r.TOOLS_SHA256, "actual_sha256": tools_hash},
        "historical_anchor": {
            "source_experiment": "A0.1R-partial-block-residual",
            "cached_tokens": EXPECTED_CACHED_TOKENS,
            "lcp": EXPECTED_LCP,
            "span": list(EXPECTED_SPAN),
            "prefix_sha256": EXPECTED_PREFIX_SHA256,
        },
        "vllm": {
            "version": a01r.VLLM_VERSION,
            "distribution_version": vllm_distribution_version,
            "commit": vllm_commit,
            "source_root": vllm_source_root,
        },
        "model": {
            "name": a01r.MODEL,
            "revision": a01r.MODEL_REVISION,
            "tokenizer_revision": a01r.MODEL_REVISION,
            "local_snapshot": model_snapshot,
        },
        "engine": {
            "prefix_caching": True,
            "chunked_prefill": True,
            "speculative_decoding": False,
            "connector": None,
            "disable_log_stats": False,
        },
        "gpu": dict(gpu),
    }


def _accounting(r0: Mapping[str, Any], r1: Mapping[str, Any] | None, verdict: PreflightVerdict | None) -> Dict[str, Any]:
    return {
        "mapping_id": "request-output-num-cached-tokens-vllm-0.25.1",
        "request_field": "vllm.outputs.RequestOutput.num_cached_tokens",
        "r0": {"num_cached_tokens": r0["num_cached_tokens"], "cold_expected": 0},
        "r1": None if r1 is None else {
            "num_cached_tokens": r1["num_cached_tokens"],
            "expected_cached_tokens": EXPECTED_CACHED_TOKENS,
            "status": None if verdict is None else verdict.status,
        },
    }


def _publish_invalid_after_r0(destination: Path, manifest: Mapping[str, Any], r0: Mapping[str, Any], error: Exception) -> str:
    invalid_manifest = dict(manifest)
    invalid_manifest["status"] = "invalid_run"
    write_bundle(destination, {
        "manifest.json": invalid_manifest,
        "r0.json": dict(r0),
        "r1.json": {"failure": str(error)},
        "accounting.json": _accounting(r0, None, None),
        "verdict.json": {"status": "invalid_run", "reason": str(error)},
    })
    return "invalid_run"


def _canonical_r1_messages(a01r: Any, fixture: Mapping[str, Any], tokenizer: Any, r0: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], Any, Dict[str, Any], str]:
    from vllm.entrypoints.chat_utils import make_tool_call_id
    from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser

    parser = Hermes2ProToolParser(tokenizer, tools=fixture["tools"])
    r0_tool = a01r._parse_one_tool_call(parser, r0["completion_text"])
    tool_call_id = make_tool_call_id()
    assistant = {
        "role": "assistant",
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": r0_tool["name"],
                "arguments": json.dumps(r0_tool["arguments"], ensure_ascii=False, separators=(",", ":")),
            },
        }],
    }
    messages = list(fixture["initial_messages"]) + [
        assistant,
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(fixture["tool_result"], ensure_ascii=False, separators=(",", ":")),
        },
        {"role": "user", "content": fixture["resume_prompt"]},
    ]
    return messages, parser, r0_tool, tool_call_id


def run_preflight(ordinal: int, attempt: int, destination: Path) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    a01r = _load_a01r_runner()
    input_hashes, project_head = _tracked_inputs()
    fixture, fixture_hash, tools_hash = a01r._load_fixture()

    import vllm
    from huggingface_hub import snapshot_download
    from vllm import LLM, SamplingParams

    vllm_distribution_version = a01r._require_vllm_version()
    vllm_commit, vllm_source_root = a01r._pinned_vllm_commit(vllm)
    model_snapshot = a01r._local_model_snapshot(snapshot_download)
    llm = LLM(**_engine_kwargs(model_snapshot))
    config = llm.llm_engine.vllm_config
    if config.cache_config.enable_prefix_caching is not True:
        raise RuntimeError("engine did not preserve enable_prefix_caching=True")
    if config.scheduler_config.enable_chunked_prefill is not True:
        raise RuntimeError("engine did not preserve enable_chunked_prefill=True")
    if getattr(config, "speculative_config", None) is not None:
        raise RuntimeError("engine did not disable speculative decoding")
    gpu = a01r._gpu_provenance()

    r0_output = a01r._one_request_output(
        llm.chat(
            fixture["initial_messages"],
            sampling_params=SamplingParams(temperature=0, max_tokens=256),
            tools=fixture["tools"],
            use_tqdm=False,
        ),
        "R0",
    )
    r0 = a01r._r0_record(r0_output)
    manifest = _base_manifest(
        ordinal=ordinal, attempt=attempt, project_head=project_head,
        input_hashes=input_hashes, a01r=a01r, fixture_hash=fixture_hash,
        tools_hash=tools_hash, model_snapshot=model_snapshot,
        vllm_distribution_version=vllm_distribution_version, vllm_commit=vllm_commit,
        vllm_source_root=vllm_source_root, gpu=gpu,
    )
    try:
        tokenizer = llm.get_tokenizer()
        if a01r._render_ids(tokenizer, fixture["initial_messages"], fixture["tools"]) != r0["prompt_token_ids"]:
            raise RuntimeError("R0 engine prompt IDs differ from complete local template render")
        r1_messages, parser, r0_tool, tool_call_id = _canonical_r1_messages(a01r, fixture, tokenizer, r0)
        r1_output = a01r._one_request_output(
            llm.chat(
                r1_messages,
                sampling_params=SamplingParams(temperature=0, max_tokens=1),
                tools=fixture["tools"],
                use_tqdm=False,
            ),
            "R1",
        )
        r1 = {
            "request_id": str(r1_output.request_id),
            "prompt_token_ids": a01r._output_ids(r1_output, "prompt_token_ids"),
            "completion_token_ids": a01r._output_ids(r1_output.outputs[0], "token_ids"),
            "num_cached_tokens": getattr(r1_output, "num_cached_tokens", None),
            "messages": r1_messages,
        }
        r1_rendered = a01r._render_text(tokenizer, r1_messages, fixture["tools"])
        initial_rendered = tokenizer.apply_chat_template(list(fixture["initial_messages"]), tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False)
        through_assistant_rendered = tokenizer.apply_chat_template(r1_messages[:len(fixture["initial_messages"]) + 1], tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False)
        assistant_start, assistant_end = message_region_from_prefixes(r1_rendered, str(initial_rendered), str(through_assistant_rendered))
        open_marker, close_marker = str(parser.tool_call_start_token), str(parser.tool_call_end_token)
        r1_span = a01r._span_for_full_render(tokenizer, r1_rendered, r1["prompt_token_ids"], open_marker, close_marker, search_start=assistant_start, search_end=assistant_end)
        r0_text = tokenizer.decode(r0["completion_token_ids"], skip_special_tokens=False, clean_up_tokenization_spaces=False)
        r0_completion_span = a01r._span_for_full_render(tokenizer, r0_text, r0["completion_token_ids"], open_marker, close_marker)
        r0_span = Span(
            start=len(r0["prompt_token_ids"]) + r0_completion_span.start,
            end=len(r0["prompt_token_ids"]) + r0_completion_span.end,
            left_boundary_expansion=r0_completion_span.left_boundary_expansion,
            right_boundary_expansion=r0_completion_span.right_boundary_expansion,
        )
        r1_envelope_start = r1_rendered.index(open_marker, assistant_start, assistant_end)
        r1_envelope_end = r1_rendered.index(close_marker, r1_envelope_start, assistant_end) + len(close_marker)
        r1_tool = a01r._parse_one_tool_call(parser, r1_rendered[r1_envelope_start:r1_envelope_end])
        if r0_tool != r1_tool:
            raise ValueError("R0 and R1 parser structures differ")
        template_hash = _sha256_bytes(str(getattr(tokenizer, "chat_template", "")).encode("utf-8"))
        if template_hash != a01r.TEMPLATE_SHA256:
            raise ValueError("active chat template SHA-256 drifted from A0.1")
        lcp = lcp_length(r0["r0_ids"], r1["prompt_token_ids"])
        span_equal = list(r0["r0_ids"][r0_span.start:r0_span.end]) == list(r1["prompt_token_ids"][r1_span.start:r1_span.end])
        prefix_hash = _sha256_bytes(json.dumps(r1["prompt_token_ids"][:EXPECTED_CACHED_TOKENS], separators=(",", ":")).encode("utf-8"))
        if (
            (r0_span.start, r0_span.end) != EXPECTED_SPAN
            or (r1_span.start, r1_span.end) != EXPECTED_SPAN
            or prefix_hash != EXPECTED_PREFIX_SHA256
        ):
            raise ValueError("span or eligible-prefix anchor drifted from A0.1R")
        verdict = decide_preflight(
            r0_cached_tokens=r0["num_cached_tokens"],
            r1_cached_tokens=r1["num_cached_tokens"],
            r0_prompt_tokens=len(r0["prompt_token_ids"]),
            r1_prompt_tokens=len(r1["prompt_token_ids"]),
            lcp=lcp,
            semantic_span_equal=span_equal,
            block_size=int(config.cache_config.block_size),
        )
    except Exception as error:
        return _publish_invalid_after_r0(destination, manifest, r0, error)

    complete_manifest = dict(manifest)
    complete_manifest.update({"status": verdict.status, "template_sha256": template_hash})
    write_bundle(destination, {
        "manifest.json": complete_manifest,
        "r0.json": {**r0, "assistant_span": r0_span.__dict__, "parser_tool": r0_tool},
        "r1.json": {**r1, "assistant_span": r1_span.__dict__, "parser_tool": r1_tool, "tool_call_id": tool_call_id},
        "accounting.json": _accounting(r0, r1, verdict),
        "verdict.json": {
            "status": verdict.status,
            "reason": verdict.reason,
            "lcp": lcp,
            "semantic_span_equal": span_equal,
            "expected_cached_tokens": EXPECTED_CACHED_TOKENS,
            "observed_cached_tokens": r1["num_cached_tokens"],
        },
    })
    return verdict.status


def main(argv: Sequence[str] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.attempt <= 0:
        raise SystemExit("--attempt must be positive")
    status = run_preflight(args.ordinal, args.attempt, destination_for(RAW_ROOT, args.ordinal, args.attempt))
    print("A0.2 chunked-prefill preflight ordinal={} attempt={} {}".format(args.ordinal, args.attempt, status))
    return 0 if status == "admission_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
