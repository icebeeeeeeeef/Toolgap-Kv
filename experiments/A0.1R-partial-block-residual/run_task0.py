#!/usr/bin/env python3
"""Run one A0.1R Task-0 stock-APC admission ordinal.

This is intentionally a one-purpose, blocking, single-request harness. It is
not an A0.2 pressure benchmark and exposes no policy or capacity knobs.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Sequence, Tuple


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from task0 import A01_TASK0_ANCHOR, Task0Verdict, decide_task0, write_task0_bundle
from toolgap_kv import a01 as a01_module
from toolgap_kv.a01 import Span, locate_span, message_region_from_prefixes


VLLM_VERSION = "0.25.1"
VLLM_COMMIT = "752a3a504485790a2e8491cacbb35c137339ad34"
MODEL = "Qwen/Qwen2.5-7B-Instruct"
MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
MAPPING_ID = "request-output-num-cached-tokens-vllm-0.25.1"
SPAN_ADAPTER_VERSION = "message-scoped-full-text-fast-tokenizer-offset-overlap-v2"
FIXTURE = REPOSITORY_ROOT / "experiments/0001-mechanism-feasibility/a0.1-fixture.json"
FIXTURE_SHA256 = "4f2131c8457cde7a7dbe46c2c610fbfeef8b1a184c77b863129e77235fe1d894"
TOOLS_SHA256 = "0b533e9e056ef9024c13ef2c495cf55afafe2abeeb56bc211e56a2fb2b3a890e"
TEMPLATE_SHA256 = "cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f"
PREFIX_ANCHOR = EXPERIMENT_DIR / "a0.1-task0-prefix-anchor.json"
SPEC = EXPERIMENT_DIR / "A0.1R-partial-block-residual-spec.md"
RAW_ROOT = EXPERIMENT_DIR / "raw"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinal", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--attempt", type=int, default=1)
    return parser.parse_args(argv)


def destination_for(raw_root: Path, ordinal: int, attempt: int) -> Path:
    if attempt <= 0:
        raise ValueError("attempt must be positive")
    return raw_root / "task-0" / "task0-o{:02d}-a{:02d}".format(ordinal, attempt)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _as_ids(value: Any) -> List[int]:
    if isinstance(value, Mapping):
        value = value.get("input_ids")
    if value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, (list, tuple)):
        raise ValueError("tokenizer did not return a token-ID sequence")
    if any(type(token_id) is not int for token_id in value):
        raise ValueError("tokenizer returned a non-integer token ID")
    return list(value)


def _as_offsets(value: Any) -> List[Tuple[int, int]]:
    if isinstance(value, Mapping):
        value = value.get("offset_mapping")
    if value and isinstance(value[0], list) and value[0] and isinstance(value[0][0], (list, tuple)):
        value = value[0]
    if not isinstance(value, (list, tuple)):
        raise ValueError("fast tokenizer did not return offset_mapping")
    return [(int(item[0]), int(item[1])) for item in value]


def _render_ids(
    tokenizer: Any,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> List[int]:
    rendered = tokenizer.apply_chat_template(
        list(messages), tools=list(tools), tokenize=True, add_generation_prompt=True
    )
    return _as_ids(rendered)


def _render_text(
    tokenizer: Any,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> str:
    rendered = tokenizer.apply_chat_template(
        list(messages), tools=list(tools), tokenize=False, add_generation_prompt=True
    )
    if not isinstance(rendered, str):
        raise ValueError("chat template did not return text")
    return rendered


def _full_encoding(tokenizer: Any, rendered: str) -> Tuple[List[int], List[Tuple[int, int]]]:
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True)
    return _as_ids(encoded), _as_offsets(encoded)


def _normal_tool_call(tool_call: Any) -> Dict[str, Any]:
    function = tool_call.function
    return {"name": str(function.name), "arguments": json.loads(str(function.arguments))}


def _parse_one_tool_call(parser: Any, text: str) -> Dict[str, Any]:
    parsed = parser.extract_tool_calls(text, None)
    if not parsed.tools_called or len(parsed.tool_calls) != 1:
        raise ValueError("Hermes parser did not return exactly one tool call")
    return _normal_tool_call(parsed.tool_calls[0])


def _pinned_vllm_commit(vllm_module: Any) -> Tuple[str, str]:
    source_roots = [Path(path).resolve() for path in getattr(vllm_module, "__path__", ())]
    module_file = getattr(vllm_module, "__file__", None)
    if module_file:
        source_roots.append(Path(module_file).resolve().parents[1])
    if not source_roots:
        raise RuntimeError("vLLM module does not expose an import path")

    observed = []
    for source_root in dict.fromkeys(source_roots):
        result = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        if result.returncode == 0:
            observed.append(commit)
            if commit == VLLM_COMMIT:
                return commit, str(source_root)
    raise RuntimeError(
        "expected vLLM commit {}, got {}".format(VLLM_COMMIT, observed)
    )


def _require_vllm_version() -> str:
    distribution_version = importlib_metadata.version("vllm")
    semantic_version = distribution_version.split("+", 1)[0]
    if semantic_version != VLLM_VERSION:
        raise RuntimeError(
            "expected vLLM {}, got {}".format(VLLM_VERSION, distribution_version)
        )
    return distribution_version


def _local_model_snapshot(snapshot_download: Any) -> str:
    """Resolve the pinned model before engine construction, without network I/O."""
    snapshot = Path(snapshot_download(
        repo_id=MODEL,
        revision=MODEL_REVISION,
        local_files_only=True,
    )).resolve()
    if not snapshot.is_dir():
        raise RuntimeError("pinned model snapshot is not a directory: {}".format(snapshot))
    return str(snapshot)


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


def _tracked_inputs() -> Tuple[Dict[str, str], str]:
    paths = (
        EXPERIMENT_DIR / "run_task0.py",
        EXPERIMENT_DIR / "task0.py",
        REPOSITORY_ROOT / "src/toolgap_kv/a01.py",
        SPEC,
        PREFIX_ANCHOR,
    )
    relative = tuple(str(path.relative_to(REPOSITORY_ROOT)) for path in paths)
    for path in relative:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=str(REPOSITORY_ROOT),
            check=True,
            capture_output=True,
        )
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *relative],
        cwd=str(REPOSITORY_ROOT),
        check=True,
    )
    project_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPOSITORY_ROOT),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return ({path: _sha256_bytes(file.read_bytes()) for path, file in zip(relative, paths)}, project_head)


def _load_fixture() -> Tuple[Dict[str, Any], str, str]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual_hash = _sha256_bytes(_canonical_json_bytes(fixture))
    if actual_hash != FIXTURE_SHA256:
        raise RuntimeError("fixture SHA-256 does not match the registered A0.1 input")
    tools_hash = _sha256_bytes(_canonical_json_bytes(fixture["tools"]))
    if tools_hash != TOOLS_SHA256:
        raise RuntimeError("tool schema SHA-256 does not match the registered A0.1 input")
    return fixture, actual_hash, tools_hash


def _output_ids(output: Any, field: str) -> List[int]:
    value = getattr(output, field, None)
    if not isinstance(value, (list, tuple)) or any(type(token_id) is not int for token_id in value):
        raise ValueError("RequestOutput.{} is not an engine-owned integer sequence".format(field))
    return list(value)


def _one_request_output(outputs: Any, name: str) -> Any:
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise ValueError("{} did not return exactly one RequestOutput".format(name))
    output = outputs[0]
    if not isinstance(getattr(output, "outputs", None), list) or len(output.outputs) != 1:
        raise ValueError("{} did not contain exactly one completion".format(name))
    return output


def _r0_record(output: Any) -> Dict[str, Any]:
    prompt_ids = _output_ids(output, "prompt_token_ids")
    completion = output.outputs[0]
    completion_ids = _output_ids(completion, "token_ids")
    return {
        "request_id": str(output.request_id),
        "prompt_token_ids": prompt_ids,
        "completion_token_ids": completion_ids,
        "completion_text": str(completion.text),
        "r0_ids": prompt_ids + completion_ids,
        "num_cached_tokens": getattr(output, "num_cached_tokens", None),
    }


def _base_manifest(
    *,
    ordinal: int,
    attempt: int,
    project_head: str,
    input_hashes: Mapping[str, str],
    fixture_hash: str,
    tools_hash: str,
    model_snapshot: str,
    vllm_distribution_version: str,
    vllm_commit: str,
    vllm_source_root: str,
    gpu: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "experiment": "A0.1R-partial-block-residual",
        "task": "stock-apc-admission",
        "execution_mode": "blocking-single-request-llm-chat",
        "ordinal": ordinal,
        "attempt": attempt,
        "argv": list(sys.argv),
        "project_head": project_head,
        "tracked_input_sha256": dict(input_hashes),
        "fixture": {"path": str(FIXTURE.relative_to(REPOSITORY_ROOT)), "expected_sha256": FIXTURE_SHA256, "actual_sha256": fixture_hash},
        "tools": {"expected_sha256": TOOLS_SHA256, "actual_sha256": tools_hash},
        "prefix_anchor": {"path": str(PREFIX_ANCHOR.relative_to(REPOSITORY_ROOT)), "sha256": _sha256_bytes(PREFIX_ANCHOR.read_bytes())},
        "vllm": {
            "version": VLLM_VERSION,
            "distribution_version": vllm_distribution_version,
            "commit": vllm_commit,
            "source_root": vllm_source_root,
        },
        "model": {
            "name": MODEL,
            "revision": MODEL_REVISION,
            "tokenizer_revision": MODEL_REVISION,
            "local_snapshot": model_snapshot,
        },
        "engine": {"prefix_caching": True, "chunked_prefill": False, "speculative_decoding": False, "connector": None},
        "gpu": dict(gpu),
        "span_adapter": {"version": SPAN_ADAPTER_VERSION, "a01_module_sha256": _sha256_bytes(Path(a01_module.__file__).read_bytes())},
    }


def _accounting(r0: Mapping[str, Any], r1: Mapping[str, Any] | None, verdict: Task0Verdict | None) -> Dict[str, Any]:
    r0_cached = r0["num_cached_tokens"]
    return {
        "mapping_id": MAPPING_ID,
        "source": {
            "request_field": "vllm.outputs.RequestOutput.num_cached_tokens",
            "local_hit_origin": "vllm.v1.core.sched.scheduler.Scheduler.schedule",
            "aggregation": "vllm.v1.metrics.stats.PrefillStats.set",
            "propagation": "vllm.v1.engine.output_processor.OutputProcessor.process_outputs",
        },
        "r0": {
            "request_id": r0["request_id"],
            "prompt_tokens": len(r0["prompt_token_ids"]),
            "num_cached_tokens": r0_cached,
            "cold_expected": 0,
            "cold_observed": r0_cached == 0,
        },
        "r1": None if r1 is None else {
            "request_id": r1["request_id"],
            "prompt_tokens": len(r1["prompt_token_ids"]),
            "num_cached_tokens": r1["num_cached_tokens"],
            "full_hit_expected": verdict.eligible_full_prefix_tokens if verdict else None,
            "full_hit_observed": verdict is not None and r1["num_cached_tokens"] == verdict.eligible_full_prefix_tokens,
            "recomputed_prompt_tokens": verdict.recomputed_prompt_tokens if verdict else None,
        },
    }


def _publish_invalid_after_r0(
    destination: Path,
    manifest: Mapping[str, Any],
    r0: Mapping[str, Any],
    error: Exception,
) -> str:
    invalid_manifest = dict(manifest)
    invalid_manifest["status"] = "invalid_run"
    write_task0_bundle(destination, {
        "manifest.json": invalid_manifest,
        "r0.json": dict(r0),
        "r1.json": {"failure": str(error)},
        "accounting.json": _accounting(r0, None, None),
        "verdict.json": {"status": "invalid_run", "reason": str(error)},
    })
    return "invalid_run"


def run_task0(ordinal: int, attempt: int, destination: Path) -> str:
    """Execute an ordinal, retaining an invalid bundle for every post-R0 failure."""
    if destination.exists():
        raise FileExistsError(destination)
    input_hashes, project_head = _tracked_inputs()
    fixture, fixture_hash, tools_hash = _load_fixture()

    import vllm
    from huggingface_hub import snapshot_download
    from vllm import LLM, SamplingParams

    vllm_distribution_version = _require_vllm_version()
    vllm_commit, vllm_source_root = _pinned_vllm_commit(vllm)
    model_snapshot = _local_model_snapshot(snapshot_download)
    llm = LLM(
        model=model_snapshot,
        tokenizer=model_snapshot,
        tensor_parallel_size=1,
        enable_prefix_caching=True,
        enable_chunked_prefill=False,
        spec_method=None,
        seed=0,
        disable_log_stats=True,
    )
    config = llm.llm_engine.vllm_config
    if config.cache_config.enable_prefix_caching is not True:
        raise RuntimeError("engine did not preserve enable_prefix_caching=True")
    if config.scheduler_config.enable_chunked_prefill is not False:
        raise RuntimeError("engine did not preserve enable_chunked_prefill=False")
    if getattr(config, "speculative_config", None) is not None:
        raise RuntimeError("engine did not disable speculative decoding")
    gpu = _gpu_provenance()

    r0_output = _one_request_output(
        llm.chat(
            fixture["initial_messages"],
            sampling_params=SamplingParams(temperature=0, max_tokens=256),
            tools=fixture["tools"],
            use_tqdm=False,
        ),
        "R0",
    )
    r0 = _r0_record(r0_output)
    manifest = _base_manifest(
        ordinal=ordinal,
        attempt=attempt,
        project_head=project_head,
        input_hashes=input_hashes,
        fixture_hash=fixture_hash,
        tools_hash=tools_hash,
        model_snapshot=model_snapshot,
        vllm_distribution_version=vllm_distribution_version,
        vllm_commit=vllm_commit,
        vllm_source_root=vllm_source_root,
        gpu=gpu,
    )
    try:
        tokenizer = llm.get_tokenizer()
        local_r0_prompt_ids = _render_ids(
            tokenizer, fixture["initial_messages"], fixture["tools"]
        )
        if local_r0_prompt_ids != r0["prompt_token_ids"]:
            raise RuntimeError(
                "R0 engine prompt IDs differ from the complete local template render"
            )
        from vllm.entrypoints.chat_utils import make_tool_call_id
        from vllm.tool_parsers.hermes_tool_parser import Hermes2ProToolParser

        parser = Hermes2ProToolParser(tokenizer, tools=fixture["tools"])
        r0_tool = _parse_one_tool_call(parser, r0["completion_text"])
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
        r1_messages = list(fixture["initial_messages"]) + [
            assistant,
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(fixture["tool_result"], ensure_ascii=False, separators=(",", ":")),
            },
            {"role": "user", "content": fixture["resume_prompt"]},
        ]
        r1_output = _one_request_output(
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
            "prompt_token_ids": _output_ids(r1_output, "prompt_token_ids"),
            "completion_token_ids": _output_ids(r1_output.outputs[0], "token_ids"),
            "num_cached_tokens": getattr(r1_output, "num_cached_tokens", None),
            "messages": r1_messages,
        }
        r1_rendered = _render_text(tokenizer, r1_messages, fixture["tools"])
        initial_rendered = tokenizer.apply_chat_template(
            list(fixture["initial_messages"]), tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False
        )
        through_assistant_rendered = tokenizer.apply_chat_template(
            r1_messages[:len(fixture["initial_messages"]) + 1], tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False
        )
        assistant_region_start, assistant_region_end = message_region_from_prefixes(
            r1_rendered, str(initial_rendered), str(through_assistant_rendered)
        )
        open_marker = str(parser.tool_call_start_token)
        close_marker = str(parser.tool_call_end_token)
        r1_span = _span_for_full_render(
            tokenizer, r1_rendered, r1["prompt_token_ids"], open_marker, close_marker,
            search_start=assistant_region_start, search_end=assistant_region_end,
        )
        r0_text = tokenizer.decode(
            r0["completion_token_ids"], skip_special_tokens=False, clean_up_tokenization_spaces=False
        )
        r0_completion_span = _span_for_full_render(
            tokenizer, r0_text, r0["completion_token_ids"], open_marker, close_marker
        )
        r0_span = Span(
            start=len(r0["prompt_token_ids"]) + r0_completion_span.start,
            end=len(r0["prompt_token_ids"]) + r0_completion_span.end,
            left_boundary_expansion=r0_completion_span.left_boundary_expansion,
            right_boundary_expansion=r0_completion_span.right_boundary_expansion,
        )
        r1_envelope_start = r1_rendered.index(open_marker, assistant_region_start, assistant_region_end)
        r1_envelope_end = r1_rendered.index(close_marker, r1_envelope_start, assistant_region_end) + len(close_marker)
        r1_tool = _parse_one_tool_call(parser, r1_rendered[r1_envelope_start:r1_envelope_end])
        if r0_tool != r1_tool:
            raise ValueError("R0 and R1 parser structures differ")
        template = str(getattr(tokenizer, "chat_template", ""))
        actual_template_hash = _sha256_bytes(template.encode("utf-8"))
        if actual_template_hash != TEMPLATE_SHA256:
            raise ValueError("active chat template SHA-256 drifted from the A0.1 pin")
        block_size = int(config.cache_config.block_size)
        verdict = decide_task0(
            r0_ids=r0["r0_ids"],
            r1_ids=r1["prompt_token_ids"],
            r0_span=r0_span,
            r1_span=r1_span,
            block_size=block_size,
            r0_cached_tokens=r0["num_cached_tokens"],
            r1_cached_tokens=r1["num_cached_tokens"],
            evidence_valid=True,
            expected_anchor=A01_TASK0_ANCHOR,
        )
    except Exception as error:
        return _publish_invalid_after_r0(destination, manifest, r0, error)

    complete_manifest = dict(manifest)
    complete_manifest.update({
        "status": verdict.status,
        "template": {"expected_sha256": TEMPLATE_SHA256, "actual_sha256": actual_template_hash},
    })
    write_task0_bundle(destination, {
        "manifest.json": complete_manifest,
        "r0.json": {**r0, "assistant_span": r0_span.__dict__, "parser_tool": r0_tool},
        "r1.json": {**r1, "rendered": r1_rendered, "assistant_span": r1_span.__dict__, "parser_tool": r1_tool, "tool_call_id": tool_call_id},
        "accounting.json": _accounting(r0, r1, verdict),
        "verdict.json": {
            "status": verdict.status,
            "reason": verdict.reason,
            "lcp": verdict.lcp,
            "eligible_full_prefix_tokens": verdict.eligible_full_prefix_tokens,
            "eligible_prefix_sha256": verdict.eligible_prefix_sha256,
            "semantic_span_equal": verdict.semantic_span_equal,
            "residual_shared_tokens": verdict.residual_shared_tokens,
            "semantic_tail_not_in_full_prefix": verdict.semantic_tail_not_in_full_prefix,
            "mapping_reaudit_required": verdict.status == "stock_apc_unavailable",
        },
    })
    return verdict.status


def main(argv: Sequence[str] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.attempt <= 0:
        raise SystemExit("--attempt must be positive")
    destination = destination_for(RAW_ROOT, args.ordinal, args.attempt)
    status = run_task0(args.ordinal, args.attempt, destination)
    print("A0.1R Task-0 ordinal={} attempt={} {}".format(args.ordinal, args.attempt, status))
    return 0 if status == "admission_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
