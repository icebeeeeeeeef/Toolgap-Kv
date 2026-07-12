import unittest

from toolgap_kv.phase0 import (
    DecisionTrace,
    LifecycleAction,
    ObservedAction,
    ToolGapEvent,
)


class LifecycleActionTest(unittest.TestCase):
    def test_parse_accepts_frozen_actions(self):
        self.assertIs(LifecycleAction.parse("retain"), LifecycleAction.RETAIN)
        self.assertIs(LifecycleAction.parse("offload"), LifecycleAction.OFFLOAD)
        self.assertIs(LifecycleAction.parse("recompute"), LifecycleAction.RECOMPUTE)

    def test_parse_rejects_unknown_action(self):
        with self.assertRaisesRegex(ValueError, "unsupported lifecycle action"):
            LifecycleAction.parse("spill")


class ToolGapEventTest(unittest.TestCase):
    def test_event_rejects_empty_identity(self):
        with self.assertRaisesRegex(ValueError, "session_id"):
            ToolGapEvent(
                session_id="",
                turn_id=1,
                lifecycle_epoch=1,
                prefix_tokens=2048,
                requested_action=LifecycleAction.OFFLOAD,
                cache_salt="run-001",
            )

    def test_event_rejects_non_positive_prefix(self):
        with self.assertRaisesRegex(ValueError, "prefix_tokens"):
            ToolGapEvent(
                session_id="s1",
                turn_id=1,
                lifecycle_epoch=1,
                prefix_tokens=0,
                requested_action=LifecycleAction.OFFLOAD,
                cache_salt="run-001",
            )

    def test_from_mapping_parses_action(self):
        event = ToolGapEvent.from_mapping(
            {
                "session_id": "s1",
                "turn_id": 2,
                "lifecycle_epoch": 1,
                "prefix_tokens": 8192,
                "requested_action": "recompute",
                "cache_salt": "run-003",
            }
        )
        self.assertIs(event.requested_action, LifecycleAction.RECOMPUTE)
        self.assertEqual(event.prefix_tokens, 8192)


class DecisionTraceTest(unittest.TestCase):
    def test_trace_requires_complete_token_accounting(self):
        with self.assertRaisesRegex(ValueError, "token accounting"):
            DecisionTrace(
                session_id="s1",
                lifecycle_epoch=1,
                requested_action=LifecycleAction.OFFLOAD,
                observed_action=ObservedAction.CPU_RESTORE,
                prefix_tokens=8192,
                matched_tokens=4096,
                recomputed_tokens=2048,
                kv_bytes=100,
            )

    def test_trace_accepts_cpu_restore_observation(self):
        trace = DecisionTrace(
            session_id="s1",
            lifecycle_epoch=1,
            requested_action=LifecycleAction.OFFLOAD,
            observed_action=ObservedAction.CPU_RESTORE,
            prefix_tokens=8192,
            matched_tokens=8192,
            recomputed_tokens=0,
            kv_bytes=134217728,
        )
        self.assertEqual(trace.matched_tokens, trace.prefix_tokens)


if __name__ == "__main__":
    unittest.main()
