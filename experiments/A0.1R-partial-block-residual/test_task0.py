"""CPU-only contract tests for the A0.1R stock-APC admission experiment."""

import hashlib
import io
import json
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from toolgap_kv.a01 import Span
from task0 import TASK0_BUNDLE_FILES, Task0Anchor, decide_task0, write_task0_bundle


R0_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
R1_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 99, 10]
SPAN = Span(2, 7)
TOY_ANCHOR = Task0Anchor(
    r0_span=(2, 7),
    r1_span=(2, 7),
    lcp=8,
    block_size=4,
    eligible_full_prefix_tokens=8,
    eligible_prefix_sha256="b2ddd6543011e658aaebc223b42021e89fa9a18bd1f2207f6cb68e73ca5688b3",
)
EXPERIMENT_DIR = Path(__file__).resolve().parent


class Task0VerdictTest(unittest.TestCase):
    def decide(self, *, r0_cached=0, r1_cached=8, evidence_valid=True):
        return decide_task0(
            r0_ids=R0_IDS,
            r1_ids=R1_IDS,
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=r0_cached,
            r1_cached_tokens=r1_cached,
            evidence_valid=evidence_valid,
            expected_anchor=TOY_ANCHOR,
        )

    def test_exact_full_hit_passes(self):
        verdict = self.decide()
        self.assertEqual(verdict.status, "admission_pass")
        self.assertEqual(verdict.lcp, 8)
        self.assertEqual(verdict.eligible_full_prefix_tokens, 8)
        self.assertEqual(verdict.recomputed_prompt_tokens, 2)

    def test_non_cold_r0_is_invalid(self):
        self.assertEqual(self.decide(r0_cached=4).status, "invalid_run")

    def test_short_block_aligned_r1_hit_is_unavailable(self):
        self.assertEqual(self.decide(r1_cached=4).status, "stock_apc_unavailable")

    def test_r1_hit_beyond_lcp_is_invalid(self):
        verdict = decide_task0(
            r0_ids=R0_IDS,
            r1_ids=[1, 2, 3, 4, 5, 6, 7, 8, 99, 10, 11, 12, 13],
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=12,
            evidence_valid=True,
            expected_anchor=TOY_ANCHOR,
        )
        self.assertEqual(verdict.status, "invalid_run")

    def test_missing_counter_is_invalid(self):
        self.assertEqual(self.decide(r1_cached=None).status, "invalid_run")

    def test_invalid_external_evidence_never_passes(self):
        self.assertEqual(self.decide(evidence_valid=False).status, "invalid_run")

    def test_out_of_range_span_is_invalid(self):
        verdict = decide_task0(
            r0_ids=R0_IDS,
            r1_ids=R1_IDS,
            r0_span=Span(2, 10),
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=8,
            evidence_valid=True,
            expected_anchor=TOY_ANCHOR,
        )
        self.assertEqual(verdict.status, "invalid_run")

    def test_semantic_mismatch_stops_before_admission(self):
        verdict = decide_task0(
            r0_ids=R0_IDS,
            r1_ids=[1, 2, 99, 4, 5, 6, 7, 8, 9],
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=0,
            evidence_valid=True,
            expected_anchor=TOY_ANCHOR,
        )
        self.assertEqual(verdict.status, "semantic_stop")

    def test_malformed_accounting_wins_over_semantic_mismatch(self):
        verdict = decide_task0(
            r0_ids=R0_IDS,
            r1_ids=[1, 2, 99, 4, 5, 6, 7, 8, 9],
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=3,
            evidence_valid=True,
            expected_anchor=TOY_ANCHOR,
        )
        self.assertEqual(verdict.status, "invalid_run")

    def test_non_semantic_anchor_drift_is_invalid(self):
        drifted = Task0Anchor(
            r0_span=(2, 7),
            r1_span=(2, 7),
            lcp=9,
            block_size=4,
            eligible_full_prefix_tokens=8,
            eligible_prefix_sha256=TOY_ANCHOR.eligible_prefix_sha256,
        )
        verdict = decide_task0(
            r0_ids=R0_IDS,
            r1_ids=R1_IDS,
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=8,
            evidence_valid=True,
            expected_anchor=drifted,
        )
        self.assertEqual(verdict.status, "invalid_run")

    def test_eligible_prefix_hash_drift_is_invalid(self):
        verdict = decide_task0(
            r0_ids=[42, 2, 3, 4, 5, 6, 7, 8, 9],
            r1_ids=[42, 2, 3, 4, 5, 6, 7, 8, 99, 10],
            r0_span=SPAN,
            r1_span=SPAN,
            block_size=4,
            r0_cached_tokens=0,
            r1_cached_tokens=8,
            evidence_valid=True,
            expected_anchor=TOY_ANCHOR,
        )
        self.assertEqual(verdict.status, "invalid_run")


def complete_task0_bundle():
    return {
        "manifest.json": {"experiment": "A0.1R-task-0"},
        "r0.json": {"token_ids": [1, 2]},
        "r1.json": {"prompt_token_ids": [1, 2]},
        "accounting.json": {"mapping_id": "request-output-num-cached-tokens-vllm-0.25.1"},
        "verdict.json": {"status": "admission_pass"},
    }


class Task0ArtifactTest(unittest.TestCase):
    def test_bundle_is_complete_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "task0-o01-a01"
            write_task0_bundle(destination, complete_task0_bundle())
            self.assertEqual(
                {path.name for path in destination.iterdir()}, TASK0_BUNDLE_FILES
            )
            with self.assertRaises(FileExistsError):
                write_task0_bundle(destination, complete_task0_bundle())

    def test_incomplete_bundle_is_never_published(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "task0-o01-a01"
            bundle = complete_task0_bundle()
            bundle.pop("accounting.json")
            with self.assertRaisesRegex(ValueError, "exactly"):
                write_task0_bundle(destination, bundle)
            self.assertFalse(destination.exists())


class Task0RunnerContractTest(unittest.TestCase):
    def load_runner(self):
        return runpy.run_path(
            str(EXPERIMENT_DIR / "run_task0.py"),
            run_name="a01r_task0_runner_test",
        )

    def test_import_does_not_require_vllm(self):
        self.assertIn("main", self.load_runner())

    def test_namespace_vllm_accepts_cuda_build_metadata_and_resolves_git_root(self):
        module = self.load_runner()
        namespace_vllm = SimpleNamespace(__file__=None, __path__=["/root/vllm"])
        completed = SimpleNamespace(
            returncode=0,
            stdout=module["VLLM_COMMIT"] + "\n",
        )
        with patch.object(module["importlib_metadata"], "version", return_value="0.25.1+cu128"):
            self.assertEqual(module["_require_vllm_version"](), "0.25.1+cu128")
        with patch.object(module["subprocess"], "run", return_value=completed) as run:
            self.assertEqual(
                module["_pinned_vllm_commit"](namespace_vllm),
                (module["VLLM_COMMIT"], "/root/vllm"),
            )
        self.assertEqual(run.call_args.args[0][:3], ["git", "-C", "/root/vllm"])

    def test_cli_has_no_pressure_or_policy_surface(self):
        parse_args = self.load_runner()["parse_args"]
        args = parse_args(["--ordinal", "1", "--attempt", "1"])
        self.assertEqual((args.ordinal, args.attempt), (1, 1))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_args(["--ordinal", "1", "--attempt", "1", "--m", "0.5"])

    def test_destination_encodes_registered_ordinal_and_attempt(self):
        destination_for = self.load_runner()["destination_for"]
        self.assertEqual(
            destination_for(Path("raw"), 2, 3),
            Path("raw/task-0/task0-o02-a03"),
        )

    def test_fixture_and_prefix_anchor_hashes_recompute(self):
        module = self.load_runner()
        fixture = json.loads(module["FIXTURE"].read_text(encoding="utf-8"))
        fixture_bytes = json.dumps(
            fixture,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(fixture_bytes).hexdigest(),
            module["FIXTURE_SHA256"],
        )

        prefix_anchor = json.loads(
            module["PREFIX_ANCHOR"].read_text(encoding="utf-8")
        )
        prefix_ids = prefix_anchor["prompt_token_ids"]
        self.assertEqual(
            prefix_anchor["source_r1_sha256"],
            "2ec3a16df06b93fab8b432484b156ad85dc88a2b87760c7d167a75228454274e",
        )
        self.assertEqual(len(prefix_ids), 192)
        self.assertTrue(all(type(token_id) is int for token_id in prefix_ids))
        prefix_bytes = json.dumps(prefix_ids, separators=(",", ":")).encode("utf-8")
        recomputed = hashlib.sha256(prefix_bytes).hexdigest()
        self.assertEqual(recomputed, prefix_anchor["eligible_prefix_sha256"])
        self.assertEqual(
            recomputed,
            module["A01_TASK0_ANCHOR"].eligible_prefix_sha256,
        )


if __name__ == "__main__":
    unittest.main()
