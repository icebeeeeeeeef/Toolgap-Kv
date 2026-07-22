"""CPU-only contracts for A0.2 foreground-length qualification."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr

from toolgap_kv.a01 import Span


EXPERIMENT_DIR = Path(__file__).resolve().parent


def _compact_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _passing_bundle(*, status: str = "admission_pass") -> dict[str, object]:
    target = 2048
    prompt_ids = list(range(2060))
    return {
        "manifest.json": {"experiment": "A0.2-foreground-length-qualification"},
        "fixture.json": {"sha256": "fixture-hash"},
        "r0-reproducibility.json": {
            "completion_token_ids": [[7, 8]] * 5,
        },
        "r1.json": {
            "prompt_token_ids": prompt_ids,
            "assistant_span": {"start": 2035, "end": 2055},
        },
        "accounting.json": {"r1_cached_tokens": target},
        "verdict.json": {
            "status": status,
            "target_full_prefix_tokens": target,
            "observed_full_prefix_tokens": target,
            "lcp": 2055,
            "block_size": 16,
            "r0_span": {"start": 2035, "end": 2055},
            "r1_span": {"start": 2035, "end": 2055},
        },
    }


class LengthQualificationVerdictTest(unittest.TestCase):
    def decide(self, **overrides):
        from qualification import decide_qualification

        values = {
            "r0_cached_tokens": 0,
            "r1_cached_tokens": 2048,
            "r0_prompt_tokens": 2035,
            "r1_prompt_tokens": 2111,
            "r0_completion_id_sequences": [[7, 8]] * 5,
            "lcp": 2055,
            "semantic_span_equal": True,
            "r0_span": Span(2035, 2055),
            "r1_span": Span(2035, 2055),
            "block_size": 16,
            "target_full_prefix_tokens": 2048,
            "evidence_valid": True,
        }
        values.update(overrides)
        return decide_qualification(**values)

    def test_target_is_full_block_lcp_window_not_raw_lcp(self):
        from qualification import (
            full_block_ceiling,
            initial_prompt_center,
            initial_prompt_window,
        )

        self.assertEqual(initial_prompt_window(2048), (2027, 2042))
        self.assertEqual(initial_prompt_center(2048), 2035)
        self.assertEqual(full_block_ceiling(2063, 16), 2048)

    def test_exact_full_block_admission_passes(self):
        verdict = self.decide()

        self.assertEqual(verdict.status, "admission_pass")
        self.assertEqual(verdict.target_full_prefix_tokens, 2048)
        self.assertEqual(verdict.observed_full_prefix_tokens, 2048)

    def test_short_full_block_prefix_stops_fixture_qualification(self):
        verdict = self.decide(
            r1_cached_tokens=2032,
            lcp=2047,
            r0_span=Span(2035, 2047),
            r1_span=Span(2035, 2047),
        )

        self.assertEqual(verdict.status, "fixture_qualification_stop")

    def test_non_cold_r0_is_invalid_before_later_interpretation(self):
        verdict = self.decide(r0_cached_tokens=16, r1_cached_tokens=2032, lcp=2047)

        self.assertEqual(verdict.status, "invalid_run")

    def test_non_reproducible_r0_is_invalid(self):
        verdict = self.decide(
            r0_completion_id_sequences=[[7, 8], [7, 8], [7, 9], [7, 8], [7, 8]]
        )

        self.assertEqual(verdict.status, "invalid_run")

    def test_missing_or_malformed_counter_is_accounting_contract_change(self):
        for overrides in (
            {"r1_cached_tokens": None},
            {"r1_cached_tokens": True},
            {"r1_prompt_tokens": None},
            {"r1_cached_tokens": 2112},
            {"r1_cached_tokens": 2049},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    self.decide(**overrides).status,
                    "accounting_contract_change",
                )

    def test_semantic_mismatch_stops_before_fixture_length_interpretation(self):
        verdict = self.decide(
            semantic_span_equal=False,
            r1_cached_tokens=2032,
            lcp=2047,
        )

        self.assertEqual(verdict.status, "semantic_stop")


class LengthQualificationArtifactTest(unittest.TestCase):
    def test_bundle_is_atomic_and_refuses_overwrite(self):
        from qualification import BUNDLE_FILES, write_bundle

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "qualification-a01"
            bundle = _passing_bundle()
            write_bundle(destination, bundle)

            self.assertEqual({path.name for path in destination.iterdir()}, BUNDLE_FILES)
            with self.assertRaises(FileExistsError):
                write_bundle(destination, bundle)

    def test_incomplete_bundle_is_never_published(self):
        from qualification import write_bundle

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "qualification-a01"
            bundle = _passing_bundle()
            del bundle["r1.json"]

            with self.assertRaises(ValueError):
                write_bundle(destination, bundle)
            self.assertFalse(destination.exists())


class LengthQualificationPromotionTest(unittest.TestCase):
    def test_promotion_derives_compact_prefix_hash_from_pass_bundle(self):
        from qualification import promoted_anchor_from_bundle

        bundle = _passing_bundle()
        anchor = promoted_anchor_from_bundle(bundle)

        self.assertEqual(anchor["schema_version"], 1)
        self.assertEqual(anchor["target_full_prefix_tokens"], 2048)
        self.assertEqual(anchor["lcp"], 2055)
        self.assertEqual(anchor["r0_span"], [2035, 2055])
        self.assertEqual(anchor["r1_span"], [2035, 2055])
        self.assertEqual(
            anchor["eligible_prefix_sha256"],
            _compact_sha256(bundle["r1.json"]["prompt_token_ids"][:2048]),
        )
        self.assertEqual(
            anchor["source_bundle_sha256"],
            _compact_sha256(bundle["manifest.json"]),
        )

    def test_promotion_refuses_non_pass_bundle(self):
        from qualification import promoted_anchor_from_bundle

        with self.assertRaises(ValueError):
            promoted_anchor_from_bundle(_passing_bundle(status="fixture_qualification_stop"))


class FixturePreparationTest(unittest.TestCase):
    @staticmethod
    def base_fixture() -> dict[str, object]:
        return {
            "initial_messages": [
                {"role": "system", "content": "base system"},
                {"role": "user", "content": "What is the weather?"},
            ],
            "tools": [{"type": "function", "function": {"name": "weather"}}],
            "tool_result": {"city": "Hangzhou"},
            "resume_prompt": "Answer using the tool result.",
        }

    @staticmethod
    def one_token_per_record(messages, tools):
        del tools
        record_count = messages[0]["content"].count("record=")
        return list(range(2027 + record_count))

    @staticmethod
    def equidistant_candidates(messages, tools):
        del tools
        record_count = messages[0]["content"].count("record=")
        if record_count == 0:
            return list(range(2034))
        if record_count == 1:
            return list(range(2036))
        return list(range(2050))

    def test_builder_selects_window_center_when_reachable(self):
        from build_fixtures import build_fixture

        fixture = build_fixture(
            self.base_fixture(), 2048, render_ids=self.one_token_per_record
        )

        self.assertEqual(
            fixture["qualification"]["accepted_r0_prompt_window"], [2027, 2042]
        )
        self.assertEqual(fixture["qualification"]["prepared_r0_prompt_tokens"], 2035)
        self.assertEqual(fixture["qualification"]["archive_record_count"], 8)

    def test_builder_breaks_equal_distance_tie_with_lower_record_count(self):
        from build_fixtures import build_fixture

        fixture = build_fixture(
            self.base_fixture(), 2048, render_ids=self.equidistant_candidates
        )

        self.assertEqual(fixture["qualification"]["prepared_r0_prompt_tokens"], 2034)
        self.assertEqual(fixture["qualification"]["archive_record_count"], 0)

    def test_builder_preserves_user_tool_schema_and_tool_result(self):
        from build_fixtures import build_fixture

        base = self.base_fixture()
        fixture = build_fixture(base, 2048, render_ids=self.one_token_per_record)

        self.assertEqual(fixture["initial_messages"][-1], base["initial_messages"][-1])
        self.assertEqual(fixture["tools"], base["tools"])
        self.assertEqual(fixture["tool_result"], base["tool_result"])
        self.assertEqual(base["initial_messages"][0]["content"], "base system")

    def test_fixture_file_is_compact_json_and_refuses_overwrite(self):
        from build_fixtures import write_fixture

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "foreground-2048.json"
            write_fixture(destination, {"b": 1, "a": [2]})
            self.assertEqual(destination.read_text(encoding="utf-8"), '{"a":[2],"b":1}\n')
            with self.assertRaises(FileExistsError):
                write_fixture(destination, {"a": 1})


class FixturePreparationRunnerContractTest(unittest.TestCase):
    def load_builder(self):
        return runpy.run_path(
            str(EXPERIMENT_DIR / "build_fixtures.py"),
            run_name="a02_foreground_fixture_builder_test",
        )

    def test_import_does_not_require_transformers_or_vllm(self):
        self.assertIn("main", self.load_builder())

    def test_cli_accepts_only_registered_target_and_output(self):
        parse_args = self.load_builder()["parse_args"]
        args = parse_args(["--target", "2048", "--output", "fixtures/foreground-2048.json"])
        self.assertEqual((args.target, args.output), (2048, "fixtures/foreground-2048.json"))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--target", "17", "--output", "x.json"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--target", "2048", "--output", "x.json", "--padding", "override"])


class QualificationRunnerContractTest(unittest.TestCase):
    def load_runner(self):
        return runpy.run_path(
            str(EXPERIMENT_DIR / "run_qualification.py"),
            run_name="a02_foreground_qualification_runner_test",
        )

    def test_import_does_not_require_vllm(self):
        self.assertIn("run_parent", self.load_runner())

    def test_public_cli_accepts_only_target_and_attempt(self):
        parse_args = self.load_runner()["parse_args"]
        args = parse_args(["--target", "2048", "--attempt", "1"])
        self.assertEqual((args.target, args.attempt), (2048, 1))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--target", "2048", "--attempt", "1", "--seed", "7"])

    def test_destination_encodes_target_and_attempt(self):
        destination_for = self.load_runner()["destination_for"]
        self.assertEqual(
            destination_for(Path("raw"), 8192, 2),
            Path("raw/qualification/L8192/qualification-a02"),
        )

    def test_worker_environment_forces_hnd_layout(self):
        worker_environment = self.load_runner()["worker_environment"]
        self.assertEqual(
            worker_environment({"UNCHANGED": "yes"}),
            {"UNCHANGED": "yes", "VLLM_KV_CACHE_LAYOUT": "HND"},
        )

    def test_all_three_tracked_fixture_paths_are_fixed(self):
        tracked_fixture_paths = self.load_runner()["tracked_fixture_paths"]
        self.assertEqual(
            tracked_fixture_paths(),
            (
                Path("fixtures/foreground-2048.json"),
                Path("fixtures/foreground-8192.json"),
                Path("fixtures/foreground-16384.json"),
            ),
        )

    def test_parsed_worker_result_retains_stderr_tail_for_raw_evidence(self):
        runner = self.load_runner()
        worker_result = runner["_worker_result"]
        prefix = runner["WORKER_RESULT_PREFIX"]

        record = worker_result(
            prefix + '{"worker_index":1,"status":"failure","error":"engine failed"}',
            1,
            0,
            "engine-core root cause",
            123,
        )

        self.assertEqual(record["process_stderr_tail"], "engine-core root cause")


class QualificationWorkerReductionTest(unittest.TestCase):
    @staticmethod
    def worker_records() -> list[dict[str, object]]:
        prompt_ids = list(range(2035))
        completion_ids = list(range(5000, 5020))
        r0 = {
            "prompt_token_ids": prompt_ids,
            "completion_token_ids": completion_ids,
            "num_cached_tokens": 0,
        }
        records = [
            {"worker_index": index, "status": "ok", "r0": r0}
            for index in range(1, 6)
        ]
        records[-1] = {
            "worker_index": 5,
            "status": "ok",
            "r0": r0,
            "r1": {
                "prompt_token_ids": prompt_ids + completion_ids + [6000, 6001],
                "completion_token_ids": [7000],
                "num_cached_tokens": 2048,
                "r0_span": [2035, 2055],
                "r1_span": [2035, 2055],
                "parser_structures_equal": True,
                "block_size": 16,
            },
        }
        return records

    def test_reduction_derives_admission_from_engine_owned_id_sequences(self):
        from run_qualification import reduce_worker_records

        verdict, evidence = reduce_worker_records(2048, self.worker_records())

        self.assertEqual(verdict.status, "admission_pass")
        self.assertEqual(evidence["lcp"], 2055)
        self.assertTrue(evidence["semantic_span_equal"])
        self.assertEqual(evidence["r0_completion_id_sequences"], [list(range(5000, 5020))] * 5)

    def test_reduction_preserves_child_failure_as_invalid_run(self):
        from run_qualification import reduce_worker_records

        records = self.worker_records()
        records[2] = {"worker_index": 3, "status": "failure", "error": "engine failed"}
        verdict, evidence = reduce_worker_records(2048, records)

        self.assertEqual(verdict.status, "invalid_run")
        self.assertEqual(evidence["worker_failure"], "engine failed")

    def test_reduction_rejects_parser_structure_mismatch_before_token_verdict(self):
        from run_qualification import reduce_worker_records

        records = self.worker_records()
        records[-1]["r1"]["parser_structures_equal"] = False
        verdict, _ = reduce_worker_records(2048, records)

        self.assertEqual(verdict.status, "invalid_run")

    def test_reduction_preserves_malformed_r0_accounting_as_contract_change(self):
        from run_qualification import reduce_worker_records

        records = self.worker_records()
        records[1]["r0"]["num_cached_tokens"] = None
        verdict, _ = reduce_worker_records(2048, records)

        self.assertEqual(verdict.status, "accounting_contract_change")

    def test_reduction_keeps_empty_semantic_span_as_invalid_run(self):
        from run_qualification import reduce_worker_records

        records = self.worker_records()
        records[-1]["r1"]["r0_span"] = [2035, 2035]
        verdict, _ = reduce_worker_records(2048, records)

        self.assertEqual(verdict.status, "invalid_run")


if __name__ == "__main__":
    unittest.main()
