"""Frozen contracts for Phase 0 mechanism-feasibility experiments.

This module intentionally contains no vLLM imports. The source audit must prove
the engine integration boundary before runtime abstractions are added here.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class LifecycleAction(str, Enum):
    RETAIN = "retain"
    OFFLOAD = "offload"
    RECOMPUTE = "recompute"

    @classmethod
    def parse(cls, value: str) -> "LifecycleAction":
        try:
            return cls(value)
        except ValueError as error:
            supported = ", ".join(action.value for action in cls)
            raise ValueError(
                "unsupported lifecycle action {!r}; expected one of: {}".format(
                    value, supported
                )
            ) from error


class ObservedAction(str, Enum):
    GPU_HIT = "gpu_hit"
    CPU_RESTORE = "cpu_restore"
    RECOMPUTE = "recompute"

    @classmethod
    def parse(cls, value: str) -> "ObservedAction":
        try:
            return cls(value)
        except ValueError as error:
            supported = ", ".join(action.value for action in cls)
            raise ValueError(
                "unsupported observed action {!r}; expected one of: {}".format(
                    value, supported
                )
            ) from error


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(name))


def _require_integer(name: str, value: int, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(name, minimum))


@dataclass(frozen=True)
class ToolGapEvent:
    session_id: str
    turn_id: int
    lifecycle_epoch: int
    prefix_tokens: int
    requested_action: LifecycleAction
    cache_salt: str

    def __post_init__(self) -> None:
        _require_non_empty("session_id", self.session_id)
        _require_non_empty("cache_salt", self.cache_salt)
        _require_integer("turn_id", self.turn_id, 1)
        _require_integer("lifecycle_epoch", self.lifecycle_epoch, 1)
        _require_integer("prefix_tokens", self.prefix_tokens, 1)
        if not isinstance(self.requested_action, LifecycleAction):
            raise ValueError("requested_action must be a LifecycleAction")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ToolGapEvent":
        return cls(
            session_id=value["session_id"],
            turn_id=value["turn_id"],
            lifecycle_epoch=value["lifecycle_epoch"],
            prefix_tokens=value["prefix_tokens"],
            requested_action=LifecycleAction.parse(value["requested_action"]),
            cache_salt=value["cache_salt"],
        )


@dataclass(frozen=True)
class DecisionTrace:
    session_id: str
    lifecycle_epoch: int
    requested_action: LifecycleAction
    observed_action: ObservedAction
    prefix_tokens: int
    matched_tokens: int
    recomputed_tokens: int
    kv_bytes: int
    fallback_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _require_non_empty("session_id", self.session_id)
        _require_integer("lifecycle_epoch", self.lifecycle_epoch, 1)
        _require_integer("prefix_tokens", self.prefix_tokens, 1)
        _require_integer("matched_tokens", self.matched_tokens, 0)
        _require_integer("recomputed_tokens", self.recomputed_tokens, 0)
        _require_integer("kv_bytes", self.kv_bytes, 0)
        if not isinstance(self.requested_action, LifecycleAction):
            raise ValueError("requested_action must be a LifecycleAction")
        if not isinstance(self.observed_action, ObservedAction):
            raise ValueError("observed_action must be an ObservedAction")
        if self.matched_tokens + self.recomputed_tokens != self.prefix_tokens:
            raise ValueError(
                "token accounting must satisfy matched_tokens + "
                "recomputed_tokens == prefix_tokens"
            )
        if self.observed_action in (
            ObservedAction.GPU_HIT,
            ObservedAction.CPU_RESTORE,
        ) and self.recomputed_tokens != 0:
            raise ValueError("cache-hit paths cannot report recomputed tokens")
        if (
            self.observed_action is ObservedAction.RECOMPUTE
            and self.matched_tokens != 0
        ):
            raise ValueError("the Phase 0 recompute path must be a full cache miss")
        if self.fallback_reason is not None:
            _require_non_empty("fallback_reason", self.fallback_reason)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DecisionTrace":
        return cls(
            session_id=value["session_id"],
            lifecycle_epoch=value["lifecycle_epoch"],
            requested_action=LifecycleAction.parse(value["requested_action"]),
            observed_action=ObservedAction.parse(value["observed_action"]),
            prefix_tokens=value["prefix_tokens"],
            matched_tokens=value["matched_tokens"],
            recomputed_tokens=value["recomputed_tokens"],
            kv_bytes=value["kv_bytes"],
            fallback_reason=value.get("fallback_reason"),
        )
