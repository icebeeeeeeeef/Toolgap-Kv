#!/usr/bin/env python3
"""Run one five-process engine-truth A0.2 foreground qualification target."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXPERIMENT_DIR.parents[1]
RAW_ROOT = EXPERIMENT_DIR / "raw"
PARENT_ENV = "TOOLGAP_A02_QUALIFICATION_PARENT"
TARGETS = (2048, 8192, 16384)
A01R_DIR = REPOSITORY_ROOT / "experiments/A0.1R-partial-block-residual"
A01R_RUNNER = A01R_DIR / "run_task0.py"
FIXTURE_DIR = EXPERIMENT_DIR / "fixtures"
WORKER_RESULT_PREFIX = "A02_QUALIFICATION_WORKER_RESULT="
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from qualification import LengthQualificationVerdict, decide_qualification
from toolgap_kv.a01 import Span, lcp_length


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse only the public, reproducible qualification invocation surface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, choices=TARGETS, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    return parser.parse_args(argv)


def _parse_worker_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, choices=TARGETS, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--_worker-index", type=int, choices=(1, 2, 3, 4, 5), required=True)
    return parser.parse_args(argv)


def destination_for(raw_root: Path, target: int, attempt: int) -> Path:
    if target not in TARGETS:
        raise ValueError("unsupported target: {}".format(target))
    if attempt <= 0:
        raise ValueError("attempt must be positive")
    return raw_root / "qualification" / "L{}".format(target) / "qualification-a{:02d}".format(attempt)


def worker_environment(base: Mapping[str, str]) -> dict[str, str]:
    environment = dict(base)
    environment["VLLM_KV_CACHE_LAYOUT"] = "HND"
    return environment


def tracked_fixture_paths() -> tuple[Path, Path, Path]:
    return tuple(Path("fixtures/foreground-{}.json".format(target)) for target in TARGETS)  # type: ignore[return-value]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_a01r_runner() -> Any:
    if str(A01R_DIR) not in sys.path:
        sys.path.insert(0, str(A01R_DIR))
    spec = importlib.util.spec_from_file_location("a02_qualification_a01r", A01R_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen A0.1R runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _tracked_inputs() -> tuple[dict[str, str], str]:
    paths = (
        EXPERIMENT_DIR / "run_qualification.py",
        EXPERIMENT_DIR / "qualification.py",
        EXPERIMENT_DIR / "build_fixtures.py",
        REPOSITORY_ROOT / "src/toolgap_kv/a01.py",
        A01R_DIR / "run_task0.py",
        A01R_DIR / "task0.py",
        *(EXPERIMENT_DIR / path for path in tracked_fixture_paths()),
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


def _fixture_path(target: int) -> Path:
    if target not in TARGETS:
        raise ValueError("unsupported target: {}".format(target))
    return FIXTURE_DIR / "foreground-{}.json".format(target)


def _load_fixture(target: int) -> tuple[dict[str, Any], str]:
    path = _fixture_path(target)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    qualification = fixture.get("qualification")
    if not isinstance(qualification, Mapping):
        raise ValueError("fixture qualification block is missing")
    if qualification.get("target_full_prefix_tokens") != target:
        raise ValueError("fixture target does not match invocation")
    window = qualification.get("accepted_r0_prompt_window")
    prepared = qualification.get("prepared_r0_prompt_tokens")
    if (
        not isinstance(window, list)
        or len(window) != 2
        or any(type(value) is not int for value in window)
        or type(prepared) is not int
        or not window[0] <= prepared <= window[1]
    ):
        raise ValueError("fixture qualification metadata is malformed")
    return fixture, _sha256_bytes(path.read_bytes())


def _invalid(target: int, reason: str, evidence: Mapping[str, Any]) -> tuple[LengthQualificationVerdict, dict[str, Any]]:
    return (
        LengthQualificationVerdict("invalid_run", reason, target, None),
        dict(evidence),
    )


def _ids(value: Any) -> list[int] | None:
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        return None
    return list(value)


def _span(value: Any) -> Span | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or value[0] < 0
        or value[1] <= value[0]
    ):
        return None
    return Span(value[0], value[1])


def reduce_worker_records(
    target: int, worker_records: Sequence[Mapping[str, Any]]
) -> tuple[LengthQualificationVerdict, dict[str, Any]]:
    """Reduce five child JSON records into the single registered qualification verdict."""
    if len(worker_records) != 5:
        return _invalid(target, "parent did not receive five worker records", {})
    if [record.get("worker_index") for record in worker_records] != [1, 2, 3, 4, 5]:
        return _invalid(target, "worker indices are not the registered sequence", {})
    for record in worker_records:
        if record.get("status") != "ok":
            return _invalid(target, "a worker failed", {"worker_failure": str(record.get("error", "unknown worker failure"))})

    r0_records = [record.get("r0") for record in worker_records]
    if any(not isinstance(record, Mapping) for record in r0_records):
        return _invalid(target, "worker omitted its R0 record", {})
    typed_r0_records = [record for record in r0_records if isinstance(record, Mapping)]
    completion_sequences = [_ids(record.get("completion_token_ids")) for record in typed_r0_records]
    prompt_sequences = [_ids(record.get("prompt_token_ids")) for record in typed_r0_records]
    cached_values = [record.get("num_cached_tokens") for record in typed_r0_records]
    if any(value is None for value in completion_sequences + prompt_sequences):
        return _invalid(target, "worker emitted non-integer engine token IDs", {})
    if any(type(value) is not int for value in cached_values):
        return (
            LengthQualificationVerdict(
                "accounting_contract_change",
                "worker emitted malformed R0 cached-token accounting",
                target,
                None,
            ),
            {},
        )
    if any(value != 0 for value in cached_values):
        return _invalid(target, "a fresh worker R0 was not cold", {})

    fifth = worker_records[-1]
    r1 = fifth.get("r1")
    if not isinstance(r1, Mapping):
        return _invalid(target, "fifth worker omitted canonical R1", {})
    r1_prompt = _ids(r1.get("prompt_token_ids"))
    r0_span = _span(r1.get("r0_span"))
    r1_span = _span(r1.get("r1_span"))
    block_size = r1.get("block_size")
    if (
        r1_prompt is None
        or r0_span is None
        or r1_span is None
        or type(block_size) is not int
        or r1.get("parser_structures_equal") is not True
    ):
        return _invalid(target, "canonical R1 evidence is malformed", {})

    r0_prompt = prompt_sequences[-1]
    r0_completion = completion_sequences[-1]
    assert r0_prompt is not None and r0_completion is not None
    r0_ids = r0_prompt + r0_completion
    if r0_span.end > len(r0_ids) or r1_span.end > len(r1_prompt):
        return _invalid(target, "semantic span is outside engine-owned IDs", {})
    lcp = lcp_length(r0_ids, r1_prompt)
    semantic_span_equal = r0_ids[r0_span.start:r0_span.end] == r1_prompt[r1_span.start:r1_span.end]
    evidence = {
        "lcp": lcp,
        "semantic_span_equal": semantic_span_equal,
        "r0_completion_id_sequences": completion_sequences,
        "r0_prompt_tokens": len(r0_prompt),
        "r1_prompt_tokens": len(r1_prompt),
        "r0_span": [r0_span.start, r0_span.end],
        "r1_span": [r1_span.start, r1_span.end],
        "block_size": block_size,
    }
    verdict = decide_qualification(
        r0_cached_tokens=cached_values[-1],
        r1_cached_tokens=r1.get("num_cached_tokens"),
        r0_prompt_tokens=len(r0_prompt),
        r1_prompt_tokens=len(r1_prompt),
        r0_completion_id_sequences=completion_sequences,
        lcp=lcp,
        semantic_span_equal=semantic_span_equal,
        r0_span=r0_span,
        r1_span=r1_span,
        block_size=block_size,
        target_full_prefix_tokens=target,
        evidence_valid=True,
    )
    return verdict, evidence


def _engine_kwargs(model_snapshot: str) -> dict[str, Any]:
    return {
        "model": model_snapshot,
        "tokenizer": model_snapshot,
        "tensor_parallel_size": 1,
        "enable_prefix_caching": True,
        "enable_chunked_prefill": True,
        "seed": 0,
        "disable_log_stats": False,
    }


def _output_ids(output: Any, field: str) -> list[int]:
    value = getattr(output, field, None)
    if not isinstance(value, (list, tuple)) or any(type(token) is not int for token in value):
        raise ValueError("RequestOutput.{} is not an engine-owned integer sequence".format(field))
    return list(value)


def _one_request_output(outputs: Any, name: str) -> Any:
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise ValueError("{} did not return exactly one RequestOutput".format(name))
    output = outputs[0]
    if not isinstance(getattr(output, "outputs", None), list) or len(output.outputs) != 1:
        raise ValueError("{} did not contain exactly one completion".format(name))
    return output


def _r0_record(output: Any) -> dict[str, Any]:
    prompt_ids = _output_ids(output, "prompt_token_ids")
    completion = output.outputs[0]
    completion_ids = _output_ids(completion, "token_ids")
    return {
        "request_id": str(output.request_id),
        "prompt_token_ids": prompt_ids,
        "completion_token_ids": completion_ids,
        "completion_text": str(completion.text),
        "num_cached_tokens": getattr(output, "num_cached_tokens", None),
    }


def _canonical_r1_messages(
    a01r: Any, fixture: Mapping[str, Any], tokenizer: Any, r0: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], Any, dict[str, Any], str]:
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


def _r1_record(a01r: Any, fixture: Mapping[str, Any], llm: Any, r0: Mapping[str, Any]) -> dict[str, Any]:
    from vllm import SamplingParams
    from toolgap_kv.a01 import message_region_from_prefixes

    tokenizer = llm.get_tokenizer()
    local_r0_ids = a01r._render_ids(tokenizer, fixture["initial_messages"], fixture["tools"])
    if local_r0_ids != r0["prompt_token_ids"]:
        raise ValueError("R0 engine prompt IDs differ from complete local template render")
    messages, parser, r0_tool, tool_call_id = _canonical_r1_messages(a01r, fixture, tokenizer, r0)
    output = _one_request_output(
        llm.chat(
            messages,
            sampling_params=SamplingParams(temperature=0, max_tokens=1),
            tools=fixture["tools"],
            use_tqdm=False,
        ),
        "R1",
    )
    prompt_ids = _output_ids(output, "prompt_token_ids")
    completion_ids = _output_ids(output.outputs[0], "token_ids")
    rendered = a01r._render_text(tokenizer, messages, fixture["tools"])
    initial_rendered = tokenizer.apply_chat_template(
        list(fixture["initial_messages"]), tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False
    )
    through_assistant = tokenizer.apply_chat_template(
        messages[:len(fixture["initial_messages"]) + 1], tools=list(fixture["tools"]), tokenize=False, add_generation_prompt=False
    )
    assistant_start, assistant_end = message_region_from_prefixes(
        rendered, str(initial_rendered), str(through_assistant)
    )
    open_marker = str(parser.tool_call_start_token)
    close_marker = str(parser.tool_call_end_token)
    r1_span = a01r._span_for_full_render(
        tokenizer, rendered, prompt_ids, open_marker, close_marker,
        search_start=assistant_start, search_end=assistant_end,
    )
    r0_text = tokenizer.decode(
        r0["completion_token_ids"], skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    r0_completion_span = a01r._span_for_full_render(
        tokenizer, r0_text, r0["completion_token_ids"], open_marker, close_marker
    )
    r0_span = Span(
        start=len(r0["prompt_token_ids"]) + r0_completion_span.start,
        end=len(r0["prompt_token_ids"]) + r0_completion_span.end,
        left_boundary_expansion=r0_completion_span.left_boundary_expansion,
        right_boundary_expansion=r0_completion_span.right_boundary_expansion,
    )
    envelope_start = rendered.index(open_marker, assistant_start, assistant_end)
    envelope_end = rendered.index(close_marker, envelope_start, assistant_end) + len(close_marker)
    r1_tool = a01r._parse_one_tool_call(parser, rendered[envelope_start:envelope_end])
    return {
        "request_id": str(output.request_id),
        "prompt_token_ids": prompt_ids,
        "completion_token_ids": completion_ids,
        "num_cached_tokens": getattr(output, "num_cached_tokens", None),
        "messages": messages,
        "tool_call_id": tool_call_id,
        "r0_span": [r0_span.start, r0_span.end],
        "r1_span": [r1_span.start, r1_span.end],
        "parser_structures_equal": r0_tool == r1_tool,
        "r0_tool": r0_tool,
        "r1_tool": r1_tool,
        "template_sha256": _sha256_bytes(str(getattr(tokenizer, "chat_template", "")).encode("utf-8")),
    }


def _worker_record(target: int, attempt: int, worker_index: int) -> dict[str, Any]:
    """Run R0 in a fresh process; worker five also emits canonical R1 evidence."""
    del attempt
    if os.environ.get("VLLM_KV_CACHE_LAYOUT") != "HND":
        raise RuntimeError("worker was not started with VLLM_KV_CACHE_LAYOUT=HND")
    a01r = _load_a01r_runner()
    fixture, fixture_sha256 = _load_fixture(target)

    import vllm
    from huggingface_hub import snapshot_download
    from vllm import LLM, SamplingParams

    distribution_version = importlib_metadata.version("vllm")
    vllm_version = a01r._require_vllm_version()
    vllm_commit, vllm_source_root = a01r._pinned_vllm_commit(vllm)
    model_snapshot = a01r._local_model_snapshot(snapshot_download)
    llm = LLM(**_engine_kwargs(model_snapshot))
    config = llm.llm_engine.vllm_config
    if config.cache_config.enable_prefix_caching is not True:
        raise RuntimeError("engine did not preserve enable_prefix_caching=True")
    if config.scheduler_config.enable_chunked_prefill is not True:
        raise RuntimeError("engine did not preserve enable_chunked_prefill=True")
    if getattr(config, "speculative_config", None) is not None:
        raise RuntimeError("engine unexpectedly enabled speculative decoding")

    output = _one_request_output(
        llm.chat(
            fixture["initial_messages"],
            sampling_params=SamplingParams(temperature=0, max_tokens=256),
            tools=fixture["tools"],
            use_tqdm=False,
        ),
        "R0",
    )
    r0 = _r0_record(output)
    qualification = fixture["qualification"]
    if len(r0["prompt_token_ids"]) != qualification["prepared_r0_prompt_tokens"]:
        raise ValueError("engine R0 prompt length does not equal committed tokenizer fixture length")
    low, high = qualification["accepted_r0_prompt_window"]
    if not low <= len(r0["prompt_token_ids"]) <= high:
        raise ValueError("engine R0 prompt length lies outside registered fixture window")
    record: dict[str, Any] = {
        "worker_index": worker_index,
        "status": "ok",
        "pid": os.getpid(),
        "fixture_sha256": fixture_sha256,
        "r0": r0,
        "vllm": {
            "version": vllm_version,
            "distribution_version": distribution_version,
            "commit": vllm_commit,
            "source_root": vllm_source_root,
        },
        "model": {
            "name": a01r.MODEL,
            "revision": a01r.MODEL_REVISION,
            "local_snapshot": model_snapshot,
        },
        "engine": {
            "prefix_caching": True,
            "chunked_prefill": True,
            "speculative_decoding": False,
            "connector": None,
            "disable_log_stats": False,
            "block_size": int(config.cache_config.block_size),
            "kv_cache_layout": os.environ["VLLM_KV_CACHE_LAYOUT"],
        },
        "gpu": a01r._gpu_provenance(),
    }
    if worker_index == 5:
        r1 = _r1_record(a01r, fixture, llm, r0)
        r1["block_size"] = int(config.cache_config.block_size)
        record["r1"] = r1
    return record


def _worker_main(args: argparse.Namespace) -> int:
    try:
        record = _worker_record(args.target, args.attempt, args._worker_index)
    except Exception as error:
        record = {
            "worker_index": args._worker_index,
            "status": "failure",
            "pid": os.getpid(),
            "error": "{}: {}".format(type(error).__name__, error),
        }
    print(WORKER_RESULT_PREFIX + json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0


def _worker_result(stdout: str, worker_index: int, returncode: int, stderr: str, pid: int) -> dict[str, Any]:
    stdout_tail = "\n".join(
        line for line in stdout.splitlines() if not line.startswith(WORKER_RESULT_PREFIX)
    )[-4000:]
    for line in reversed(stdout.splitlines()):
        if line.startswith(WORKER_RESULT_PREFIX):
            try:
                record = json.loads(line[len(WORKER_RESULT_PREFIX):])
            except json.JSONDecodeError:
                break
            if isinstance(record, dict):
                record["process_returncode"] = returncode
                record["process_stderr_tail"] = stderr[-4000:]
                record["process_stdout_tail"] = stdout_tail
                return record
    return {
        "worker_index": worker_index,
        "status": "failure",
        "pid": pid,
        "error": "worker process returned {} without a parseable result; stderr={}".format(
            returncode, stderr[-4000:]
        ),
        "process_returncode": returncode,
        "process_stderr_tail": stderr[-4000:],
        "process_stdout_tail": stdout_tail,
    }


def _manifest(
    target: int,
    attempt: int,
    project_head: str,
    input_hashes: Mapping[str, str],
    fixture_sha256: str,
    worker_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    fifth = worker_records[-1] if worker_records else {}
    return {
        "experiment": "A0.2-foreground-length-qualification",
        "task": "five-process-stock-apc-admission",
        "target_full_prefix_tokens": target,
        "attempt": attempt,
        "project_head": project_head,
        "tracked_input_sha256": dict(input_hashes),
        "fixture": {
            "path": str(_fixture_path(target).relative_to(REPOSITORY_ROOT)),
            "sha256": fixture_sha256,
        },
        "execution_mode": "five-sequential-fresh-os-processes",
        "worker_pids": [record.get("pid") for record in worker_records],
        "vllm": fifth.get("vllm"),
        "model": fifth.get("model"),
        "engine": fifth.get("engine"),
        "gpu": fifth.get("gpu"),
    }


def _bundle_files(
    manifest: Mapping[str, Any],
    fixture: Mapping[str, Any],
    worker_records: Sequence[Mapping[str, Any]],
    verdict: LengthQualificationVerdict,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    r0_records = [record.get("r0") for record in worker_records]
    fifth = worker_records[-1] if worker_records else {}
    r1 = fifth.get("r1") if isinstance(fifth, Mapping) else None
    return {
        "manifest.json": dict(manifest),
        "fixture.json": dict(fixture),
        "r0-reproducibility.json": {
            "workers": list(worker_records),
            "completion_token_id_sha256": [
                None if not isinstance(record, Mapping) or not isinstance(record.get("r0"), Mapping)
                else _sha256_bytes(_canonical_json_bytes(record["r0"].get("completion_token_ids")))
                for record in worker_records
            ],
        },
        "r1.json": r1 if isinstance(r1, Mapping) else {"failure": evidence.get("worker_failure", verdict.reason)},
        "accounting.json": {
            "mapping_id": "request-output-num-cached-tokens-vllm-0.25.1",
            "request_field": "vllm.outputs.RequestOutput.num_cached_tokens",
            "r0": r0_records,
            "r1": r1,
        },
        "verdict.json": {**asdict(verdict), **dict(evidence)},
    }


def run_parent(target: int, attempt: int) -> str:
    destination = destination_for(RAW_ROOT, target, attempt)
    if destination.exists():
        raise FileExistsError("refusing to overwrite raw qualification bundle: {}".format(destination))
    input_hashes, project_head = _tracked_inputs()
    fixture, fixture_sha256 = _load_fixture(target)
    worker_records: list[dict[str, Any]] = []
    for worker_index in range(1, 6):
        environment = worker_environment(os.environ)
        environment[PARENT_ENV] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--target", str(target),
                "--attempt", str(attempt),
                "--_worker-index", str(worker_index),
            ],
            cwd=str(REPOSITORY_ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        record = _worker_result(stdout, worker_index, process.returncode, stderr, process.pid)
        worker_records.append(record)
        if record.get("status") != "ok":
            break

    verdict, evidence = reduce_worker_records(target, worker_records)
    manifest = _manifest(target, attempt, project_head, input_hashes, fixture_sha256, worker_records)
    manifest["status"] = verdict.status
    from qualification import write_bundle

    write_bundle(destination, _bundle_files(manifest, fixture, worker_records, verdict, evidence))
    return verdict.status


def main(argv: Sequence[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if os.environ.get(PARENT_ENV) == "1":
        return _worker_main(_parse_worker_args(arguments))
    args = parse_args(arguments)
    status = run_parent(args.target, args.attempt)
    print("A0.2 foreground qualification target={} attempt={} {}".format(args.target, args.attempt, status))
    return 0 if status == "admission_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
