import json
import runpy
import tempfile
import unittest
from pathlib import Path

from toolgap_kv.a01 import (
    REQUIRED_BUNDLE_FILES,
    Span,
    classify_mismatch,
    decide,
    full_block_ceiling,
    lcp_length,
    locate_span,
    write_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "experiments/0001-mechanism-feasibility/a0.1-fixture.json"


def complete_bundle():
    return {
        "manifest.json": {"status": "pass"},
        "span_adapter.json": {"open_marker": "<tool_call>"},
        "template.jinja": "template",
        "r0.json": {"token_ids": [1, 2]},
        "r1.json": {"token_ids": [1, 2]},
        "verdict.json": {"status": "pass"},
    }


class A01TokenLogicTest(unittest.TestCase):
    def test_lcp_and_full_block_ceiling(self):
        self.assertEqual(lcp_length([1, 2, 3], [1, 2, 9]), 2)
        self.assertEqual(full_block_ceiling(10, 4), 8)

    def test_mismatch_region_uses_r1_semantic_coordinates(self):
        self.assertEqual(classify_mismatch(1, 5, Span(2, 4)), "before_assistant_semantic")
        self.assertEqual(classify_mismatch(2, 5, Span(2, 4)), "assistant_semantic")
        self.assertEqual(classify_mismatch(4, 5, Span(2, 4)), "after_assistant_semantic_or_r0_exhausted")

    def test_span_expands_to_whole_boundary_tokens(self):
        span = locate_span(
            "x<tool>{}</tool>y",
            "<tool>",
            "</tool>",
            [(0, 2), (2, 9), (9, 17)],
        )
        self.assertEqual((span.start, span.end), (0, 3))
        self.assertTrue(span.left_boundary_expansion)
        self.assertTrue(span.right_boundary_expansion)

    def test_marker_must_be_unique_and_non_nested(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            locate_span("plain", "<tool>", "</tool>", [(0, 5)])
        with self.assertRaisesRegex(ValueError, "nested"):
            locate_span("<tool><tool></tool></tool>", "<tool>", "</tool>", [(0, 26)])

    def test_structurally_valid_token_difference_is_serialization_stop(self):
        verdict = decide(
            r0_ids=[1, 2, 3],
            r1_ids=[1, 9, 3],
            r0_span=Span(1, 2),
            r1_span=Span(1, 2),
            block_size=1,
            evidence_valid=True,
        )
        self.assertEqual(verdict.status, "serialization_stop")
        self.assertEqual(verdict.mismatch_region, "assistant_semantic")

    def test_pass_requires_full_block_coverage_of_semantic_end(self):
        verdict = decide(
            r0_ids=[1, 2, 3, 4, 5],
            r1_ids=[1, 2, 3, 4, 9],
            r0_span=Span(1, 4),
            r1_span=Span(1, 4),
            block_size=2,
            evidence_valid=True,
        )
        self.assertEqual(verdict.status, "pass")
        self.assertEqual(verdict.reusable_full_block_ceiling, 4)

    def test_invalid_evidence_never_becomes_token_verdict(self):
        verdict = decide(
            r0_ids=[1],
            r1_ids=[1],
            r0_span=Span(0, 1),
            r1_span=Span(0, 1),
            block_size=1,
            evidence_valid=False,
        )
        self.assertEqual(verdict.status, "invalid_run")


class A01ArtifactTest(unittest.TestCase):
    def test_bundle_refuses_overwrite_and_never_publishes_partial_output(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "run-1"
            write_bundle(destination, complete_bundle())
            self.assertEqual(
                {path.name for path in destination.iterdir()}, REQUIRED_BUNDLE_FILES
            )
            with self.assertRaises(FileExistsError):
                write_bundle(destination, complete_bundle())

    def test_bundle_rejects_missing_evidence_before_publication(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "run-1"
            incomplete = complete_bundle()
            incomplete.pop("verdict.json")
            with self.assertRaisesRegex(ValueError, "exactly"):
                write_bundle(destination, incomplete)
            self.assertFalse(destination.exists())

    def test_fixture_contains_no_tool_call_id(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertNotIn("tool_call_id", json.dumps(fixture))

    def test_runner_module_import_does_not_require_vllm(self):
        module = runpy.run_path(
            str(ROOT / "scripts/run_a01.py"), run_name="a01_runner_test"
        )
        self.assertIn("main", module)


if __name__ == "__main__":
    unittest.main()
