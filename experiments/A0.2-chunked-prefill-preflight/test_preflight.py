"""CPU-only contracts for the supported chunked-prefill admission gate."""

from pathlib import Path
import io
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr


EXPERIMENT_DIR = Path(__file__).resolve().parent


class PreflightVerdictTest(unittest.TestCase):
    def test_exact_registered_accounting_contract_passes(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=0,
            r1_cached_tokens=192,
            lcp=199,
            semantic_span_equal=True,
            block_size=16,
        )

        self.assertEqual(verdict.status, "admission_pass")
        self.assertEqual(verdict.expected_cached_tokens, 192)

    def test_changed_cached_token_mapping_pauses_as_contract_change(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=0,
            r1_cached_tokens=176,
            lcp=199,
            semantic_span_equal=True,
            block_size=16,
        )

        self.assertEqual(verdict.status, "accounting_contract_change")

    def test_non_cold_r0_is_invalid_before_accounting_interpretation(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=16,
            r1_cached_tokens=176,
            lcp=199,
            semantic_span_equal=True,
            block_size=16,
        )

        self.assertEqual(verdict.status, "invalid_run")

    def test_semantic_drift_stops_before_accounting_interpretation(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=0,
            r1_cached_tokens=192,
            lcp=199,
            semantic_span_equal=False,
            block_size=16,
        )

        self.assertEqual(verdict.status, "semantic_stop")

    def test_lcp_anchor_drift_is_invalid_even_when_it_is_longer(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=0,
            r1_cached_tokens=192,
            lcp=200,
            semantic_span_equal=True,
            block_size=16,
        )

        self.assertEqual(verdict.status, "invalid_run")

    def test_counter_above_prompt_length_is_invalid_not_contract_change(self):
        from preflight import decide_preflight

        verdict = decide_preflight(
            r0_cached_tokens=0,
            r1_cached_tokens=256,
            r1_prompt_tokens=249,
            lcp=199,
            semantic_span_equal=True,
            block_size=16,
        )

        self.assertEqual(verdict.status, "invalid_run")


class PreflightArtifactTest(unittest.TestCase):
    def test_bundle_is_atomic_and_refuses_overwrite(self):
        from preflight import BUNDLE_FILES, write_bundle

        bundle = {
            "manifest.json": {"experiment": "A0.2-chunked-prefill-preflight"},
            "r0.json": {"token_ids": [1]},
            "r1.json": {"token_ids": [1]},
            "accounting.json": {"r1_cached_tokens": 192},
            "verdict.json": {"status": "admission_pass"},
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "preflight-o01-a01"
            write_bundle(destination, bundle)
            self.assertEqual({path.name for path in destination.iterdir()}, BUNDLE_FILES)
            with self.assertRaises(FileExistsError):
                write_bundle(destination, bundle)


class PreflightRunnerContractTest(unittest.TestCase):
    def load_runner(self):
        return runpy.run_path(
            str(EXPERIMENT_DIR / "run_preflight.py"),
            run_name="a02_chunked_preflight_runner_test",
        )

    def test_import_does_not_require_vllm(self):
        self.assertIn("main", self.load_runner())

    def test_engine_enables_supported_chunked_prefill_and_keeps_accounting(self):
        kwargs = self.load_runner()["_engine_kwargs"]("/models/pinned")
        self.assertEqual(kwargs["model"], "/models/pinned")
        self.assertEqual(kwargs["tokenizer"], "/models/pinned")
        self.assertTrue(kwargs["enable_chunked_prefill"])
        self.assertFalse(kwargs["disable_log_stats"])

    def test_cli_has_no_pressure_or_policy_surface(self):
        parse_args = self.load_runner()["parse_args"]
        args = parse_args(["--ordinal", "1", "--attempt", "1"])
        self.assertEqual((args.ordinal, args.attempt), (1, 1))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--ordinal", "1", "--attempt", "1", "--m", "0.5"])

    def test_destination_keeps_attempts_immutable(self):
        destination_for = self.load_runner()["destination_for"]
        self.assertEqual(
            destination_for(Path("raw"), 2, 3),
            Path("raw/preflight/preflight-o02-a03"),
        )


if __name__ == "__main__":
    unittest.main()
