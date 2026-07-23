"""CPU-only contracts for the frozen A0.2 stock-sufficiency matrix."""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr
import io


class RegisteredScheduleTest(unittest.TestCase):
    def test_schedule_has_exactly_ninety_items_and_pair_local_order(self):
        from a02 import registered_schedule

        schedule = registered_schedule()

        self.assertEqual(len(schedule), 90)
        self.assertEqual([item.ordinal for item in schedule], list(range(1, 91)))
        self.assertEqual(
            {(item.length, item.band, item.pair) for item in schedule},
            {
                (length, band, pair)
                for length in (2048, 8192, 16384)
                for band in ("low", "target", "overload")
                for pair in range(1, 6)
            },
        )
        for offset in range(0, 90, 2):
            first, second = schedule[offset : offset + 2]
            self.assertEqual(
                (first.length, first.band, first.pair, first.nonce),
                (second.length, second.band, second.pair, second.nonce),
            )
            self.assertEqual({first.policy, second.policy}, {"S0", "S1"})
            self.assertEqual((first.policy, second.policy), tuple(first.order))
            self.assertEqual(first.order, second.order)

    def test_schedule_is_deterministic_and_has_no_free_dimensions(self):
        from a02 import registered_schedule, schedule_sha256

        first = registered_schedule()
        second = registered_schedule()

        self.assertEqual(first, second)
        self.assertEqual(schedule_sha256(first), schedule_sha256(second))
        self.assertEqual(
            {(item.band, item.m_numerator, item.m_denominator) for item in first},
            {("low", 1, 2), ("target", 11, 10), ("overload", 13, 10)},
        )


class CalibrationContractTest(unittest.TestCase):
    def test_calibration_counts_foreground_inside_working_set(self):
        from a02 import build_calibration

        calibration = build_calibration(
            gpu_capacity_blocks=4096,
            block_size=16,
            block_bytes=458752,
            host_available_bytes=8 * (1 << 30),
        )

        by_cell = {
            (cell["length"], cell["band"]): cell
            for cell in calibration["cells"]
        }
        low_2048 = by_cell[(2048, "low")]
        self.assertEqual(low_2048["working_set_target_blocks"], 2048)
        self.assertEqual(low_2048["foreground_full_prefix_blocks"], 128)
        self.assertEqual(low_2048["builder_target_blocks"], 1920)
        self.assertEqual(calibration["s1_required_cpu_bytes"], 3 * 4096 * 458752 // 2)
        self.assertEqual(calibration["s1_kv_offloading_size_gib"], 3)
        self.assertEqual(calibration["status"], "valid")

    def test_non_positive_builder_or_insufficient_dram_is_invalid_configuration(self):
        from a02 import build_calibration

        no_builder = build_calibration(
            gpu_capacity_blocks=1024,
            block_size=16,
            block_bytes=458752,
            host_available_bytes=16 * (1 << 30),
        )
        insufficient_dram = build_calibration(
            gpu_capacity_blocks=4096,
            block_size=16,
            block_bytes=458752,
            host_available_bytes=1 << 30,
        )

        self.assertEqual(no_builder["status"], "invalid_configuration")
        self.assertIn("builder_target_blocks", no_builder["reasons"][0])
        self.assertEqual(insufficient_dram["status"], "invalid_configuration")
        self.assertIn("host_available_bytes", insufficient_dram["reasons"][-1])


class PayloadContractTest(unittest.TestCase):
    def test_payloads_cover_exact_blocks_and_have_unique_first_blocks(self):
        from payloads import build_payload_plan

        plan = build_payload_plan(
            total_blocks=530,
            block_size=16,
            nonce="cell-nonce",
            usable_token_ids=list(range(100, 300)),
            foreground_first_block=list(range(16)),
            payload_block_cap=128,
            active_probe_count=2,
        )

        self.assertEqual(sum(item.blocks for item in plan), 530)
        self.assertEqual([item.blocks for item in plan], [128, 128, 128, 128, 9, 9])
        self.assertEqual(sum(item.role == "active_probe" for item in plan), 2)
        first_blocks = {tuple(item.prompt_token_ids[:16]) for item in plan}
        self.assertEqual(len(first_blocks), len(plan))
        self.assertNotIn(tuple(range(16)), first_blocks)
        self.assertTrue(all(len(item.prompt_token_ids) == item.blocks * 16 for item in plan))

    def test_payload_plan_is_byte_deterministic_for_a_pair(self):
        from payloads import build_payload_plan, payload_plan_sha256

        kwargs = dict(
            total_blocks=64,
            block_size=16,
            nonce="shared-pair-nonce",
            usable_token_ids=list(range(100, 300)),
            foreground_first_block=list(range(16)),
            payload_block_cap=16,
            active_probe_count=2,
        )
        left = build_payload_plan(**kwargs)
        right = build_payload_plan(**kwargs)

        self.assertEqual(left, right)
        self.assertEqual(payload_plan_sha256(left), payload_plan_sha256(right))


class ArtifactContractTest(unittest.TestCase):
    def test_bundle_is_exact_atomic_and_refuses_overwrite(self):
        from a02 import BUNDLE_FILES, write_bundle

        bundle = {name: {"name": name} for name in BUNDLE_FILES}
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "run-a01"
            write_bundle(destination, bundle)

            self.assertEqual({path.name for path in destination.iterdir()}, BUNDLE_FILES)
            with self.assertRaises(FileExistsError):
                write_bundle(destination, bundle)

    def test_bundle_rejects_missing_file_without_publication(self):
        from a02 import BUNDLE_FILES, write_bundle

        bundle = {name: {"name": name} for name in BUNDLE_FILES}
        bundle.pop("probe.json")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "run-a01"
            with self.assertRaises(ValueError):
                write_bundle(destination, bundle)
            self.assertFalse(destination.exists())

    def test_bundle_json_is_stable_and_machine_readable(self):
        from a02 import BUNDLE_FILES, write_bundle

        bundle = {name: {"z": 2, "a": 1} for name in BUNDLE_FILES}
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "run-a01"
            write_bundle(destination, bundle)
            loaded = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(loaded, {"a": 1, "z": 2})


class ForegroundOracleTest(unittest.TestCase):
    def setUp(self):
        self.anchor = {
            "schema_version": 1,
            "target_full_prefix_tokens": 2048,
            "block_size": 16,
            "lcp": 2059,
            "r0_span": [2038, 2058],
            "r1_span": [2038, 2058],
            "eligible_prefix_sha256": "unused",
        }
        self.r0_ids = list(range(2038)) + list(range(7000, 7021))
        self.r1_ids = list(self.r0_ids) + list(range(8000, 8050))
        from a02 import token_ids_sha256

        self.anchor["eligible_prefix_sha256"] = token_ids_sha256(self.r1_ids[:2048])

    def guard(self, **overrides):
        from a02 import evaluate_foreground

        values = {
            "anchor": self.anchor,
            "r0_prompt_token_ids": self.r0_ids[:2038],
            "r0_completion_token_ids": self.r0_ids[2038:],
            "r1_prompt_token_ids": self.r1_ids,
            "r0_span": [2038, 2058],
            "r1_span": [2038, 2058],
            "r0_cached_tokens": 0,
            "r1_cached_tokens": 2048,
        }
        values.update(overrides)
        return evaluate_foreground(**values)

    def test_anchor_exactly_matches_and_preserves_total_cached_counter(self):
        observation = self.guard()

        self.assertEqual(observation.status, "valid")
        self.assertEqual(observation.total_cached_tokens, 2048)
        self.assertEqual(observation.recomputed_prefix_tokens, 0)

    def test_block_aligned_pressure_miss_is_valid_observation(self):
        observation = self.guard(r1_cached_tokens=0)

        self.assertEqual(observation.status, "valid")
        self.assertEqual(observation.recomputed_prefix_tokens, 2048)

    def test_anchor_drift_is_invalid_before_performance_interpretation(self):
        changed = list(self.r1_ids)
        changed[100] += 1
        observation = self.guard(r1_prompt_token_ids=changed, r1_cached_tokens=0)

        self.assertEqual(observation.status, "invalid_run")
        self.assertIn("anchor", observation.reason)

    def test_malformed_counter_is_accounting_contract_change(self):
        for value in (None, True, -1, 17, 2064):
            with self.subTest(value=value):
                self.assertEqual(
                    self.guard(r1_cached_tokens=value).status,
                    "accounting_contract_change",
                )


class RunVerdictTest(unittest.TestCase):
    def decide(self, **overrides):
        from a02 import decide_run

        values = {
            "foreground_status": "valid",
            "policy": "S0",
            "target_prefix_tokens": 2048,
            "total_cached_tokens": 0,
            "local_cached_tokens": 0,
            "external_cached_tokens": 0,
            "builder_target_blocks": 100,
            "builder_observed_blocks": 100,
            "active_probe_decode_alive": 1,
            "connector_load_bytes": 0,
            "transfer_overlap_observable": False,
        }
        values.update(overrides)
        return decide_run(**values)

    def test_source_accounting_classifies_s0_full_recompute(self):
        verdict = self.decide()

        self.assertEqual(verdict.status, "valid_observation")
        self.assertEqual(verdict.foreground_path, "full_recompute")

    def test_source_accounting_classifies_local_and_external_hits(self):
        local = self.decide(
            total_cached_tokens=2048,
            local_cached_tokens=2048,
        )
        external = self.decide(
            policy="S1",
            total_cached_tokens=2048,
            external_cached_tokens=2048,
            connector_load_bytes=1024,
        )

        self.assertEqual(local.foreground_path, "gpu_local_hit")
        self.assertEqual(external.foreground_path, "cpu_restore")

    def test_total_and_source_accounting_mismatch_is_contract_change(self):
        verdict = self.decide(
            total_cached_tokens=2048,
            local_cached_tokens=1024,
            external_cached_tokens=0,
        )

        self.assertEqual(verdict.status, "accounting_contract_change")

    def test_missing_source_accounting_is_inconclusive_not_fabricated_hit(self):
        verdict = self.decide(
            total_cached_tokens=2048,
            local_cached_tokens=None,
            external_cached_tokens=None,
        )

        self.assertEqual(verdict.status, "inconclusive")
        self.assertEqual(verdict.foreground_path, "source_unobservable")

    def test_failed_pressure_or_probe_precondition_is_inconclusive(self):
        short_builder = self.decide(builder_observed_blocks=99)
        dead_probe = self.decide(active_probe_decode_alive=0)

        self.assertEqual(short_builder.status, "inconclusive")
        self.assertEqual(dead_probe.status, "inconclusive")

    def test_s1_external_tokens_require_connector_load_evidence(self):
        verdict = self.decide(
            policy="S1",
            total_cached_tokens=2048,
            external_cached_tokens=2048,
            connector_load_bytes=0,
        )

        self.assertEqual(verdict.status, "inconclusive")

    def test_s0_cannot_report_external_tokens(self):
        verdict = self.decide(
            total_cached_tokens=2048,
            external_cached_tokens=2048,
        )

        self.assertEqual(verdict.status, "accounting_contract_change")


class CalibrationRunnerContractTest(unittest.TestCase):
    def test_import_does_not_require_vllm(self):
        namespace = runpy.run_path(
            str(Path(__file__).with_name("run_calibration.py")),
            run_name="a02_calibration_import",
        )

        self.assertIn("run_calibration", namespace)

    def test_public_cli_accepts_only_attempt(self):
        from run_calibration import parse_args

        self.assertEqual(parse_args(["--attempt", "2"]).attempt, 2)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--length", "2048"])

    def test_destination_is_immutable_attempt_path(self):
        from run_calibration import destination_for

        root = Path("raw")
        self.assertEqual(
            destination_for(root, 3),
            Path("raw/calibration/calibration-a03/calibration.json"),
        )
        with self.assertRaises(ValueError):
            destination_for(root, 0)

    def test_s0_engine_kwargs_freeze_fairness_pins(self):
        from run_calibration import engine_kwargs

        kwargs = engine_kwargs("/model")

        self.assertEqual(kwargs["model"], "/model")
        self.assertIs(kwargs["enable_prefix_caching"], True)
        self.assertIs(kwargs["enable_chunked_prefill"], True)
        self.assertEqual(kwargs["block_size"], 16)
        self.assertEqual(kwargs["max_model_len"], 32768)
        self.assertNotIn("kv_offloading_size", kwargs)

    def test_qwen_block_bytes_formula_is_explicit(self):
        from run_calibration import kv_block_bytes

        self.assertEqual(
            kv_block_bytes(
                num_layers=28,
                num_kv_heads=4,
                head_size=128,
                element_size=2,
                block_size=16,
            ),
            917504,
        )


class RuntimeObservationContractTest(unittest.TestCase):
    def test_foreground_r0_honors_eos_while_pressure_requests_can_ignore_it(self):
        import inspect
        from runtime import collect_request

        parameter = inspect.signature(collect_request).parameters["ignore_eos"]
        self.assertIs(parameter.default, True)
        source = Path(__file__).with_name("run_matrix.py").read_text(encoding="utf-8")
        self.assertIn("max_tokens=256,\n            ignore_eos=False,", source)

    def test_prompt_source_records_sum_without_losing_local_external_split(self):
        from runtime import summarize_prompt_sources

        summary = summarize_prompt_sources(
            [
                {"computed": 32, "local_cache_hit": 16, "external_kv_transfer": 0, "total": 48},
                {"computed": 0, "local_cache_hit": 0, "external_kv_transfer": 64, "total": 64},
            ]
        )

        self.assertEqual(summary["computed_tokens"], 32)
        self.assertEqual(summary["local_cached_tokens"], 16)
        self.assertEqual(summary["external_cached_tokens"], 64)
        self.assertEqual(summary["total_prompt_tokens"], 112)
        self.assertEqual(summary["total_cached_tokens"], 80)

    def test_prompt_source_invariant_failure_is_rejected(self):
        from runtime import summarize_prompt_sources

        with self.assertRaises(ValueError):
            summarize_prompt_sources(
                [{"computed": 10, "local_cache_hit": 5, "external_kv_transfer": 0, "total": 14}]
            )

    def test_connector_stats_reduce_known_load_and_store_counters(self):
        from runtime import reduce_connector_stats

        payload = {
            "types": {
                "vllm:kv_offload_load_bytes": "counter",
                "vllm:kv_offload_load_time": "counter",
                "vllm:kv_offload_store_bytes": "counter",
            },
            "data": {
                "vllm:kv_offload_load_bytes": {(): 1024},
                "vllm:kv_offload_load_time": {(): 0.25},
                "vllm:kv_offload_store_bytes": {(): 4096},
            },
        }

        self.assertEqual(
            reduce_connector_stats(payload),
            {"load_bytes": 1024, "load_time_seconds": 0.25, "store_bytes": 4096},
        )


class PreflightOracleTest(unittest.TestCase):
    def test_probe_lead_is_frozen_from_pilot_window_midpoint(self):
        from a02 import select_probe_lead_offset

        offset = select_probe_lead_offset(
            first_token_delays=[0.10, 0.12, 0.11],
            finish_delays=[0.40, 0.50, 0.45],
        )

        self.assertAlmostEqual(offset, 0.30)

    def test_probe_preflight_requires_nine_of_ten(self):
        from a02 import decide_probe_preflight

        self.assertEqual(decide_probe_preflight([1] * 9 + [0]).status, "valid")
        self.assertEqual(decide_probe_preflight([1] * 8 + [0, 0]).status, "workload_spec_stop")

    def test_connector_preflight_requires_config_capacity_and_observed_load(self):
        from a02 import decide_connector_preflight

        passed = decide_connector_preflight(
            resolved_connector="OffloadingConnector",
            gpu_capacity_blocks=3151,
            expected_gpu_capacity_blocks=3151,
            configured_cpu_bytes=5 * (1 << 30),
            required_cpu_bytes=4336582656,
            external_cached_tokens=2048,
            connector_load_bytes=2048 * 917504 // 16,
        )
        no_load = decide_connector_preflight(
            resolved_connector="OffloadingConnector",
            gpu_capacity_blocks=3151,
            expected_gpu_capacity_blocks=3151,
            configured_cpu_bytes=5 * (1 << 30),
            required_cpu_bytes=4336582656,
            external_cached_tokens=0,
            connector_load_bytes=0,
        )

        self.assertEqual(passed.status, "valid")
        self.assertEqual(no_load.status, "connector_observability_stop")
        self.assertIs(passed.transfer_overlap_observable, False)


class PreflightRunnerContractTest(unittest.TestCase):
    def test_import_does_not_require_vllm(self):
        namespace = runpy.run_path(
            str(Path(__file__).with_name("run_preflight.py")),
            run_name="a02_stock_preflight_import",
        )

        self.assertIn("run_preflight", namespace)

    def test_public_cli_accepts_only_attempt(self):
        from run_preflight import parse_args

        self.assertEqual(parse_args(["--attempt", "2"]).attempt, 2)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--policy", "S1"])

    def test_destination_is_one_immutable_gate_bundle(self):
        from run_preflight import destination_for

        self.assertEqual(
            destination_for(Path("raw"), 2),
            Path("raw/preflight/preflight-a02"),
        )
        with self.assertRaises(ValueError):
            destination_for(Path("raw"), 0)

    def test_s1_diff_is_only_native_offloading_configuration(self):
        from run_preflight import policy_engine_kwargs

        s0 = policy_engine_kwargs("/model", "S0", 5)
        s1 = policy_engine_kwargs("/model", "S1", 5)
        difference = {key for key in set(s0) | set(s1) if s0.get(key) != s1.get(key)}

        self.assertEqual(difference, {"kv_offloading_size", "kv_offloading_backend"})
        self.assertEqual(s1["kv_offloading_size"], 5)
        self.assertEqual(s1["kv_offloading_backend"], "native")


class MatrixRunnerContractTest(unittest.TestCase):
    def test_import_does_not_require_vllm(self):
        namespace = runpy.run_path(
            str(Path(__file__).with_name("run_matrix.py")),
            run_name="a02_matrix_import",
        )

        self.assertIn("run_matrix", namespace)

    def test_public_cli_exposes_only_registered_ordinal_and_attempt(self):
        from run_matrix import parse_args

        args = parse_args(["--ordinal", "41", "--attempt", "2"])
        self.assertEqual((args.ordinal, args.attempt), (41, 2))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--ordinal", "1", "--length", "2048"])

    def test_destination_encodes_schedule_identity_and_attempt(self):
        from a02 import registered_schedule
        from run_matrix import destination_for

        item = registered_schedule()[40]
        self.assertEqual(item.ordinal, 41)
        self.assertEqual(
            destination_for(Path("raw"), item, 2),
            Path(
                "raw/matrix/L8192/target/pair-01/"
                f"ordinal-041-{item.policy}-a02"
            ),
        )

    def test_registered_item_lookup_refuses_out_of_range(self):
        from run_matrix import schedule_item

        self.assertEqual(schedule_item(1).ordinal, 1)
        self.assertEqual(schedule_item(90).ordinal, 90)
        for ordinal in (0, 91):
            with self.assertRaises(ValueError):
                schedule_item(ordinal)

    def test_timing_uses_engine_monotonic_events(self):
        from run_matrix import request_timing

        class Metrics:
            queued_ts = 10.0
            scheduled_ts = 10.2
            first_token_ts = 10.7
            last_token_ts = 11.0

        timing = request_timing(Metrics())

        self.assertAlmostEqual(timing["queue_delay_seconds"], 0.2)
        self.assertAlmostEqual(timing["prefill_seconds"], 0.5)
        self.assertAlmostEqual(timing["ttft_seconds"], 0.7)
        self.assertAlmostEqual(timing["service_seconds"], 0.5)


class BudgetGateContractTest(unittest.TestCase):
    def test_budget_estimate_is_conservative_and_capped_at_twelve_gpu_hours(self):
        from a02 import decide_budget

        valid = decide_budget(representative_run_seconds=100.0)
        over = decide_budget(representative_run_seconds=400.0)

        self.assertEqual(valid.status, "valid")
        self.assertAlmostEqual(valid.predicted_gpu_hours, 3.125)
        self.assertEqual(over.status, "budget_review_stop")
        self.assertAlmostEqual(over.predicted_gpu_hours, 12.5)

    def test_budget_runner_is_non_comparative_and_has_no_matrix_knobs(self):
        namespace = runpy.run_path(
            str(Path(__file__).with_name("run_budget.py")),
            run_name="a02_budget_import",
        )
        parse_args = namespace["parse_args"]

        self.assertEqual(parse_args(["--attempt", "1"]).attempt, 1)
        self.assertEqual(namespace["REPRESENTATIVE_ORDINAL"], 42)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["--ordinal", "42"])

if __name__ == "__main__":
    unittest.main()
