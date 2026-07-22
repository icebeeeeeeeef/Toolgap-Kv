"""CPU-only contracts for A0.2 foreground-length qualification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
