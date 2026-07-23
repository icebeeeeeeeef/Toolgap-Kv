"""Minimal vLLM runtime observation adapter shared by A0.2 runners.

Importing this module is CPU-only. The custom vLLM stat logger is constructed
inside ``stat_logger_factory`` after a GPU runner has imported its pinned vLLM.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from typing import Any, Mapping, Sequence


LOAD_BYTES = "vllm:kv_offload_load_bytes"
LOAD_TIME = "vllm:kv_offload_load_time"
STORE_BYTES = "vllm:kv_offload_store_bytes"
STORE_TIME = "vllm:kv_offload_store_time"


def summarize_prompt_sources(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result = {
        "computed_tokens": 0,
        "local_cached_tokens": 0,
        "external_cached_tokens": 0,
        "total_cached_tokens": 0,
        "total_prompt_tokens": 0,
    }
    for record in records:
        values = {
            "computed_tokens": record.get("computed"),
            "local_cached_tokens": record.get("local_cache_hit"),
            "external_cached_tokens": record.get("external_kv_transfer"),
            "total_prompt_tokens": record.get("total"),
        }
        if any(type(value) is not int or value < 0 for value in values.values()):
            raise ValueError("prompt source counters must be non-negative integers")
        cached = values["local_cached_tokens"] + values["external_cached_tokens"]
        if values["computed_tokens"] + cached != values["total_prompt_tokens"]:
            raise ValueError("prompt source counters do not sum to total")
        for key, value in values.items():
            result[key] += value
        result["total_cached_tokens"] += cached
    return result


def _metric_total(payload: Mapping[str, Any], metric: str) -> int | float | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    values = data.get(metric)
    if not isinstance(values, Mapping):
        return None
    total: int | float = 0
    for value in values.values():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        total += value
    return total


def reduce_connector_stats(payload: Mapping[str, Any] | None) -> dict[str, int | float]:
    if payload is None:
        return {}
    result: dict[str, int | float] = {}
    for metric, output_name in (
        (LOAD_BYTES, "load_bytes"),
        (LOAD_TIME, "load_time_seconds"),
        (STORE_BYTES, "store_bytes"),
        (STORE_TIME, "store_time_seconds"),
    ):
        value = _metric_total(payload, metric)
        if value is not None:
            result[output_name] = value
    return result


def sum_connector_records(records: Sequence[Mapping[str, Any]]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for record in records:
        connector = record.get("connector")
        if not isinstance(connector, Mapping):
            continue
        for key, value in connector.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError("reduced connector values must be numeric")
            result[key] = result.get(key, 0) + value
    return result


@dataclass
class RequestTrace:
    request_id: str
    submit_monotonic: float | None = None
    first_token_monotonic: float | None = None
    finish_monotonic: float | None = None

    @property
    def decode_active(self) -> bool:
        return self.first_token_monotonic is not None and self.finish_monotonic is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "submit_monotonic": self.submit_monotonic,
            "first_token_monotonic": self.first_token_monotonic,
            "finish_monotonic": self.finish_monotonic,
            "first_token_delay_seconds": None
            if self.submit_monotonic is None or self.first_token_monotonic is None
            else self.first_token_monotonic - self.submit_monotonic,
            "finish_delay_seconds": None
            if self.submit_monotonic is None or self.finish_monotonic is None
            else self.finish_monotonic - self.submit_monotonic,
        }


async def collect_request(
    engine: Any,
    *,
    prompt_token_ids: Sequence[int],
    request_id: str,
    max_tokens: int,
    trace: RequestTrace | None = None,
    ignore_eos: bool = True,
) -> tuple[Any, RequestTrace]:
    """Collect one AsyncLLM request while retaining first/finish liveness."""
    from vllm import SamplingParams

    if trace is None:
        trace = RequestTrace(request_id=request_id)
    trace.submit_monotonic = time.monotonic()
    final_output = None
    async for output in engine.generate(
        {"prompt_token_ids": list(prompt_token_ids)},
        SamplingParams(temperature=0, max_tokens=max_tokens, ignore_eos=ignore_eos),
        request_id=request_id,
    ):
        if trace.first_token_monotonic is None:
            trace.first_token_monotonic = time.monotonic()
        final_output = output
    trace.finish_monotonic = time.monotonic()
    if final_output is None or not getattr(final_output, "finished", False):
        raise RuntimeError(f"request {request_id} did not produce a final RequestOutput")
    return final_output, trace


async def run_requests(
    engine: Any,
    requests: Sequence[tuple[Sequence[int], str, int]],
) -> list[tuple[Any, RequestTrace]]:
    tasks = [
        asyncio.create_task(
            collect_request(
                engine,
                prompt_token_ids=prompt_ids,
                request_id=request_id,
                max_tokens=max_tokens,
            )
        )
        for prompt_ids, request_id, max_tokens in requests
    ]
    return list(await asyncio.gather(*tasks))


class EvidenceRecorder:
    """Thread-safe snapshots of unstable-but-pinned V1 stats records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []

    def record(self, scheduler_stats: Any, iteration_stats: Any) -> None:
        prompt_sources: dict[str, int] | None = None
        if iteration_stats is not None:
            stats = iteration_stats.prompt_token_stats
            prompt_sources = {
                "computed": int(stats.computed),
                "local_cache_hit": int(stats.local_cache_hit),
                "external_kv_transfer": int(stats.external_kv_transfer),
                "cached_tokens": int(stats.cached_tokens),
                "total": int(stats.total),
            }
        connector = None
        if scheduler_stats is not None:
            connector = reduce_connector_stats(scheduler_stats.kv_connector_stats)
        with self._lock:
            self._records.append(
                {
                    "captured_monotonic": time.monotonic(),
                    "prompt_sources": prompt_sources,
                    "connector": connector,
                }
            )

    def cursor(self) -> int:
        with self._lock:
            return len(self._records)

    def since(self, cursor: int) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._records[cursor:])


def stat_logger_factory(recorder: EvidenceRecorder) -> Any:
    """Return a pinned V1 StatLogger factory sharing one evidence recorder."""
    from vllm.v1.metrics.loggers import StatLoggerBase

    class EvidenceStatLogger(StatLoggerBase):
        def __init__(self, vllm_config: Any, engine_index: int = 0):
            del vllm_config, engine_index

        def record(
            self,
            scheduler_stats: Any,
            iteration_stats: Any,
            mm_cache_stats: Any = None,
            engine_idx: int = 0,
        ) -> None:
            del mm_cache_stats, engine_idx
            recorder.record(scheduler_stats, iteration_stats)

        def log_engine_initialized(self) -> None:
            return None

    return EvidenceStatLogger
