#!/usr/bin/env python3
"""Aggregate the frozen 90-run A0.2 matrix without changing run verdicts."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
RAW_ROOT = EXPERIMENT_DIR / "raw"
RESULTS_ROOT = EXPERIMENT_DIR / "results"

if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from a02 import BUNDLE_FILES, registered_schedule, schedule_sha256
from run_matrix import destination_for


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args(argv)
    if args.attempt <= 0:
        parser.error("--attempt must be positive")
    return args


def _number(value: Any, name: str, *, nonnegative: bool = True) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _pair_map(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[int, str, int, str], Mapping[str, Any]]:
    return {
        (int(row["length"]), str(row["band"]), int(row["pair"]), str(row["policy"])): row
        for row in rows
    }


def _cell_rows(
    rows: Sequence[Mapping[str, Any]], length: int, band: str, policy: str
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if row["length"] == length and row["band"] == band and row["policy"] == policy
    ]


def _dominates_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_resume = float(left["ttft_seconds"])
    right_resume = float(right["ttft_seconds"])
    left_probe = float(left["probe_median_seconds"])
    right_probe = float(right["probe_median_seconds"])
    return (
        left_resume <= right_resume
        and left_probe <= right_probe
        and (left_resume < right_resume or left_probe < right_probe)
    )


def decide_matrix(
    rows: Sequence[Mapping[str, Any]], *, transfer_overlap_observable: bool
) -> dict[str, Any]:
    """Apply only the registered cross-run Stop/Continue/Inconclusive rules."""
    schedule = registered_schedule()
    if len(rows) != len(schedule):
        return {
            "status": "inconclusive",
            "reason": "aggregation requires exactly the registered 90 runs",
            "triggered_conditions": [],
            "cells": [],
        }

    by_ordinal = {row.get("ordinal"): row for row in rows}
    if len(by_ordinal) != len(schedule) or set(by_ordinal) != set(range(1, 91)):
        return {
            "status": "inconclusive",
            "reason": "aggregation requires exactly the registered 90 runs",
            "triggered_conditions": [],
            "cells": [],
        }
    for item in schedule:
        row = by_ordinal[item.ordinal]
        identity = (row.get("length"), row.get("band"), row.get("pair"), row.get("policy"))
        if identity != (item.length, item.band, item.pair, item.policy):
            return {
                "status": "inconclusive",
                "reason": f"ordinal {item.ordinal} does not match the registered schedule",
                "triggered_conditions": [],
                "cells": [],
            }
        if row.get("status") != "valid_observation":
            return {
                "status": "inconclusive",
                "reason": f"ordinal {item.ordinal} is not a valid observation",
                "triggered_conditions": [],
                "cells": [],
            }
        for field in ("service_seconds", "ttft_seconds", "probe_median_seconds"):
            try:
                _number(row.get(field), field)
            except ValueError as error:
                return {
                    "status": "inconclusive",
                    "reason": f"ordinal {item.ordinal}: {error}",
                    "triggered_conditions": [],
                    "cells": [],
                }

    ordered = [by_ordinal[item.ordinal] for item in schedule]
    pairs = _pair_map(ordered)
    low_baselines: dict[int, dict[str, float]] = {}
    for length in (2048, 8192, 16384):
        low = _cell_rows(ordered, length, "low", "S0")
        if len(low) != 5 or any(row["foreground_path"] != "gpu_local_hit" for row in low):
            return {
                "status": "inconclusive",
                "reason": f"L={length} low-M S0 lacks five APC-hit baseline runs",
                "triggered_conditions": [],
                "cells": [],
            }
        service = float(median(float(row["service_seconds"]) for row in low))
        low_baselines[length] = {
            "median_service_seconds": service,
            "theta_seconds": max(0.005, 0.05 * service),
        }

    cell_summaries: list[dict[str, Any]] = []
    stable_full_cells: list[dict[str, Any]] = []
    unstable_missing_cells: list[str] = []
    continue_one_cells: list[str] = []
    foreground_directions: dict[str, list[str]] = {"S0_faster": [], "S1_faster": []}

    for length in (2048, 8192, 16384):
        for band in ("low", "target", "overload"):
            s0 = _cell_rows(ordered, length, band, "S0")
            s1 = _cell_rows(ordered, length, band, "S1")
            s0_full = [row for row in s0 if row["foreground_path"] == "full_recompute"]
            missing = [row for row in s0 if int(row["total_cached_tokens"]) < length]
            summary: dict[str, Any] = {
                "length": length,
                "band": band,
                "s0_paths": {path: sum(row["foreground_path"] == path for row in s0) for path in sorted({row["foreground_path"] for row in s0})},
                "s1_paths": {path: sum(row["foreground_path"] == path for row in s1) for path in sorted({row["foreground_path"] for row in s1})},
                "s0_median_ttft_seconds": float(median(float(row["ttft_seconds"]) for row in s0)),
                "s1_median_ttft_seconds": float(median(float(row["ttft_seconds"]) for row in s1)),
                "s0_probe_p95_seconds": nearest_rank(
                    [sample for row in s0 for sample in _probe_samples(row)], 0.95
                ),
                "s0_probe_p99_seconds": nearest_rank(
                    [sample for row in s0 for sample in _probe_samples(row)], 0.99
                ),
                "s1_probe_p95_seconds": nearest_rank(
                    [sample for row in s1 for sample in _probe_samples(row)], 0.95
                ),
                "s1_probe_p99_seconds": nearest_rank(
                    [sample for row in s1 for sample in _probe_samples(row)], 0.99
                ),
                "full_s0_miss_count": len(s0_full),
                "any_s0_missing_count": len(missing),
                "delta_service_seconds": None,
                "theta_seconds": low_baselines[length]["theta_seconds"],
                "material": False,
            }
            if band != "low" and s0_full:
                delta = float(median(float(row["service_seconds"]) for row in s0_full)) - low_baselines[length]["median_service_seconds"]
                summary["delta_service_seconds"] = delta
                if len(s0_full) >= 4:
                    summary["material"] = delta > low_baselines[length]["theta_seconds"]
                    stable_full_cells.append(summary)
                else:
                    unstable_missing_cells.append(f"L={length}/{band}: full miss only {len(s0_full)}/5")
            elif band != "low" and missing:
                unstable_missing_cells.append(f"L={length}/{band}: only partial S0 misses")

            if summary["material"]:
                unrestored_pairs = 0
                s0_faster = 0
                s1_faster = 0
                for pair in range(1, 6):
                    left = pairs[(length, band, pair, "S0")]
                    right = pairs[(length, band, pair, "S1")]
                    if (
                        left["foreground_path"] == "full_recompute"
                        and int(right["total_cached_tokens"]) < length
                        and int(right["external_cached_tokens"]) == 0
                    ):
                        unrestored_pairs += 1
                    if float(left["ttft_seconds"]) < float(right["ttft_seconds"]):
                        s0_faster += 1
                    elif float(right["ttft_seconds"]) < float(left["ttft_seconds"]):
                        s1_faster += 1
                summary["unrestored_pairs"] = unrestored_pairs
                summary["s0_faster_pairs"] = s0_faster
                summary["s1_faster_pairs"] = s1_faster
                label = f"L={length}/{band}"
                if unrestored_pairs >= 4:
                    continue_one_cells.append(label)
                if s0_faster >= 4:
                    foreground_directions["S0_faster"].append(label)
                if s1_faster >= 4:
                    foreground_directions["S1_faster"].append(label)
            cell_summaries.append(summary)

    target_overload_s0 = [
        row for row in ordered if row["policy"] == "S0" and row["band"] in ("target", "overload")
    ]
    stop_one = all(int(row["total_cached_tokens"]) == int(row["length"]) for row in target_overload_s0)
    stop_two = bool(stable_full_cells) and not unstable_missing_cells and all(
        not bool(cell["material"]) for cell in stable_full_cells
    )

    dominant_policy: str | None = None
    for policy, other in (("S0", "S1"), ("S1", "S0")):
        cells_dominated = 0
        for length in (2048, 8192, 16384):
            for band in ("target", "overload"):
                count = sum(
                    _dominates_pair(
                        pairs[(length, band, pair, policy)],
                        pairs[(length, band, pair, other)],
                    )
                    for pair in range(1, 6)
                )
                cells_dominated += count >= 4
        if cells_dominated == 6:
            dominant_policy = policy
            break

    continue_three = bool(foreground_directions["S0_faster"] and foreground_directions["S1_faster"])
    triggered_stop: list[str] = []
    if stop_one:
        triggered_stop.append("stop_1_no_s0_recovery_miss")
    if stop_two:
        triggered_stop.append("stop_2_no_material_service_headroom")
    if dominant_policy is not None:
        triggered_stop.append(f"stop_4_{dominant_policy}_static_nonworse")
    # Stop 3 and Continue 2 are intentionally unavailable when overlap is false.
    if transfer_overlap_observable:
        # This pin never reaches this path; retaining a false-safe marker avoids
        # inventing a transfer-overlap oracle that the raw bundles do not carry.
        return {
            "status": "inconclusive",
            "reason": "transfer-overlap contract changed; aggregation oracle requires review",
            "triggered_conditions": [],
            "cells": cell_summaries,
        }

    triggered_continue: list[str] = []
    if continue_one_cells:
        triggered_continue.append("continue_1_unrestored_material_miss")
    if continue_three:
        triggered_continue.append("continue_3_foreground_direction_reversal")

    common = {
        "cells": cell_summaries,
        "low_m_baselines": low_baselines,
        "unrestored_material_cells": continue_one_cells,
        "foreground_direction_cells": foreground_directions,
        "transfer_overlap_observable": False,
        "disabled_conditions": ["stop_3", "continue_2_directional_tradeoff"],
    }
    if triggered_stop:
        return {
            **common,
            "status": "stop_narrow",
            "reason": "at least one registered stock-sufficiency Stop/narrow condition was met",
            "triggered_conditions": triggered_stop,
        }
    if triggered_continue:
        return {
            **common,
            "status": "continue_to_a1",
            "reason": "at least one registered candidate-addressable material gap was met",
            "triggered_conditions": triggered_continue,
        }
    return {
        **common,
        "status": "inconclusive",
        "reason": "valid runs did not satisfy a stable registered Stop or Continue condition",
        "triggered_conditions": [],
        "unstable_missing_cells": unstable_missing_cells,
    }


def nearest_rank(values: Sequence[float], probability: float) -> float:
    if not values or not 0 < probability <= 1:
        raise ValueError("nearest-rank percentile requires values and 0 < p <= 1")
    ordered = sorted(float(value) for value in values)
    return ordered[math.ceil(probability * len(ordered)) - 1]


def _probe_samples(row: Mapping[str, Any]) -> list[float]:
    values = row.get("probe_samples_seconds")
    if values is None:
        return [float(row["probe_median_seconds"])]
    if not isinstance(values, list) or not values:
        raise ValueError("probe samples must be a non-empty list")
    return [_number(value, "probe sample") for value in values]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_rows(raw_root: Path, attempt: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    hashes: dict[str, dict[str, str]] = {}
    for item in registered_schedule():
        bundle = destination_for(raw_root, item, attempt)
        names = {path.name for path in bundle.iterdir()} if bundle.is_dir() else set()
        if names != BUNDLE_FILES:
            raise ValueError(f"ordinal {item.ordinal} bundle does not contain the exact seven files")
        manifest = _load_json(bundle / "manifest.json")
        verdict = _load_json(bundle / "verdict.json")
        timing = _load_json(bundle / "timing.json")
        probe = _load_json(bundle / "probe.json")
        connector = _load_json(bundle / "connector.json")
        expected_item = json.loads(json.dumps(asdict(item)))
        if manifest.get("schedule_item") != expected_item:
            raise ValueError(f"ordinal {item.ordinal} manifest schedule identity drifted")
        if manifest.get("schedule_sha256") != schedule_sha256(registered_schedule()):
            raise ValueError(f"ordinal {item.ordinal} schedule hash drifted")
        r1_timing = timing.get("r1")
        probe_times = timing.get("active_probe_queue_plus_prefill_seconds")
        connector_stats = connector.get("stats_after_r1")
        if not isinstance(r1_timing, Mapping) or not isinstance(probe_times, list) or not probe_times:
            raise ValueError(f"ordinal {item.ordinal} timing evidence is malformed")
        if not isinstance(connector_stats, Mapping):
            raise ValueError(f"ordinal {item.ordinal} connector evidence is malformed")
        if connector.get("transfer_overlap_observable") is not False:
            raise ValueError(f"ordinal {item.ordinal} transfer-overlap contract drifted")
        normalized_probe_times = [_number(value, "probe timing") for value in probe_times]
        rows.append({
            "ordinal": item.ordinal,
            "length": item.length,
            "band": item.band,
            "pair": item.pair,
            "policy": item.policy,
            "status": verdict.get("status"),
            "foreground_path": verdict.get("foreground_path"),
            "total_cached_tokens": verdict.get("total_cached_tokens"),
            "external_cached_tokens": verdict.get("external_cached_tokens"),
            "connector_load_bytes": connector_stats.get("load_bytes", 0),
            "service_seconds": r1_timing.get("service_seconds"),
            "ttft_seconds": r1_timing.get("ttft_seconds"),
            "probe_median_seconds": float(median(normalized_probe_times)),
            "probe_samples_seconds": normalized_probe_times,
        })
        hashes[str(item.ordinal)] = {
            name: hashlib.sha256((bundle / name).read_bytes()).hexdigest()
            for name in sorted(BUNDLE_FILES)
        }
    return rows, hashes


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# A0.2 Stock Sufficiency 实验汇总",
        "",
        f"- 判决：`{summary['status']}`",
        f"- 原因：{summary['reason']}",
        f"- 触发条件：{', '.join(summary.get('triggered_conditions', [])) or '无'}",
        "- 证据范围：固定 HND、capacity-pressure 代理、Qwen2.5-7B、pinned vLLM；不代表真实 tool-gap wall-clock 负载。",
        "- `transfer_overlap_observable=false`，因此 Stop 3 与 Continue 2 未参与判决。",
        "",
        "## Cell 汇总",
        "",
        "| L | M band | S0 paths | S1 paths | Δservice (ms) | θ (ms) | material |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for cell in summary.get("cells", []):
        delta = cell.get("delta_service_seconds")
        delta_ms = "-" if delta is None else f"{1000 * float(delta):.3f}"
        lines.append(
            f"| {cell['length']} | {cell['band']} | `{json.dumps(cell['s0_paths'], sort_keys=True)}` | "
            f"`{json.dumps(cell['s1_paths'], sort_keys=True)}` | {delta_ms} | "
            f"{1000 * float(cell['theta_seconds']):.3f} | {cell['material']} |"
        )
    lines.extend([
        "",
        "## 结论边界",
        "",
        "本报告只判定 stock APC/native offload 在受控容量压力下是否留下值得进入 A1 seam 验证的候选缺口。"
        "它不证明 ToolGap runtime 已实现、性能更快、真实工具等待一定触发驱逐，或生产 workload 有同等收益。",
        "",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows, hashes = load_rows(RAW_ROOT, args.attempt)
    summary = decide_matrix(rows, transfer_overlap_observable=False)
    summary.update({
        "experiment": "A0.2-stock-sufficiency",
        "attempt": args.attempt,
        "run_count": len(rows),
        "schedule_sha256": schedule_sha256(registered_schedule()),
        "bundle_sha256": hashes,
    })
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_ROOT / "a02-matrix-summary.json"
    markdown_path = RESULTS_ROOT / "a02-matrix-summary.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError("tracked A0.2 summary already exists")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    print(f"A0.2 aggregate status={summary['status']} runs={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
