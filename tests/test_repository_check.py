import unittest
from unittest import mock

from scripts import check_repository


def make_case(name, requested_action, expected_observed_action, salt, evidence):
    return {
        "name": name,
        "event": {
            "session_id": name,
            "turn_id": 1,
            "lifecycle_epoch": 1,
            "prefix_tokens": 8192,
            "requested_action": requested_action,
            "cache_salt": salt,
        },
        "expected_observed_action": expected_observed_action,
        "required_evidence": evidence,
    }


class RepositoryWorkloadCheckTest(unittest.TestCase):
    def test_accepts_auditable_a01_negative_result(self):
        manifest = {
            "experiment_id": "0001-mechanism-feasibility",
            "claim_state": "experimentally validated",
            "result_scope": "A0.1 only: negative full-block applicability result; A0.2 and A1 are blocked",
            "engine": {
                "name": "vllm",
                "version": "0.25.1",
                "commit": "752a3a504485790a2e8491cacbb35c137339ad34",
                "commit_status": "pinned_for_A0.1_only",
            },
            "environment": {"status": "A0.1_executed"},
            "raw_data": {
                "status": "collected_locally_ignored",
                "final_run_id": "a01-20260721T190035Z-span-v2",
                "tracked_summary": "experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md",
            },
        }
        with mock.patch.object(check_repository, "load_json", return_value=manifest):
            check_repository.check_manifest()

    def test_rejects_measured_claim_without_auditable_a01_boundary(self):
        manifest = {
            "experiment_id": "0001-mechanism-feasibility",
            "claim_state": "experimentally validated",
            "engine": {"commit_status": "pinned_for_A0.1_only"},
            "environment": {"status": "A0.1_executed"},
            "raw_data": {"status": "collected_locally_ignored"},
        }
        with mock.patch.object(check_repository, "load_json", return_value=manifest):
            with self.assertRaisesRegex(ValueError, "A0.1 negative result"):
                check_repository.check_manifest()

    def test_rejects_permuted_requested_to_observed_mapping(self):
        workload = {
            "schema_version": 0,
            "cases": [
                make_case(
                    "retain-case",
                    "retain",
                    "cpu_restore",
                    "salt-1",
                    ["queue_timing"],
                ),
                make_case(
                    "offload-case",
                    "offload",
                    "recompute",
                    "salt-2",
                    ["queue_timing"],
                ),
                make_case(
                    "recompute-case",
                    "recompute",
                    "gpu_hit",
                    "salt-3",
                    ["queue_timing"],
                ),
            ],
        }

        with mock.patch.object(
            check_repository, "load_json", return_value=workload
        ) as load_json:
            with self.assertRaisesRegex(
                ValueError, "retain must expect gpu_hit"
            ):
                check_repository.check_workload()

        load_json.assert_called_once_with(
            "experiments/0001-mechanism-feasibility/workload.json"
        )

    def test_rejects_case_without_queue_timing_evidence(self):
        workload = {
            "schema_version": 0,
            "cases": [
                make_case("retain-case", "retain", "gpu_hit", "salt-1", ["hash"]),
                make_case(
                    "offload-case",
                    "offload",
                    "cpu_restore",
                    "salt-2",
                    ["queue_timing"],
                ),
                make_case(
                    "recompute-case",
                    "recompute",
                    "recompute",
                    "salt-3",
                    ["queue_timing"],
                ),
            ],
        }

        with mock.patch.object(
            check_repository, "load_json", return_value=workload
        ) as load_json:
            with self.assertRaisesRegex(
                ValueError, "retain-case must require queue_timing evidence"
            ):
                check_repository.check_workload()

        load_json.assert_called_once_with(
            "experiments/0001-mechanism-feasibility/workload.json"
        )

    def test_rejects_case_without_path_specific_evidence(self):
        workload = {
            "schema_version": 0,
            "cases": [
                make_case(
                    "retain-case",
                    "retain",
                    "gpu_hit",
                    "salt-1",
                    [
                        "queue_timing",
                        "gpu_hit_tokens",
                        "resume_first_token_ns",
                        "output_token_hash",
                    ],
                ),
                make_case(
                    "offload-case",
                    "offload",
                    "cpu_restore",
                    "salt-2",
                    [
                        "queue_timing",
                        "store_start_ns",
                        "store_end_ns",
                        "gpu_miss_tokens",
                        "restore_start_ns",
                        "restore_end_ns",
                        "resume_first_token_ns",
                        "output_token_hash",
                    ],
                ),
                make_case(
                    "recompute-case",
                    "recompute",
                    "recompute",
                    "salt-3",
                    [
                        "queue_timing",
                        "gpu_miss_tokens",
                        "cpu_miss_tokens",
                        "prefill_start_ns",
                        "prefill_end_ns",
                        "resume_first_token_ns",
                        "output_token_hash",
                    ],
                ),
            ],
        }

        with mock.patch.object(
            check_repository, "load_json", return_value=workload
        ):
            with self.assertRaisesRegex(
                ValueError,
                "offload-case missing required evidence: cpu_hit_tokens",
            ):
                check_repository.check_workload()


if __name__ == "__main__":
    unittest.main()
