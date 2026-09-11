"""Stream topology consistency."""

from __future__ import annotations

import pytest

from mansour_contracts.enums import Severity
from mansour_contracts.events import EVENT_TYPES
from mansour_contracts.streams import (
    POLICIES,
    STREAM_FOR_EVENT,
    SUBSCRIPTIONS,
    Stream,
    policy_for,
)


def test_every_event_type_has_a_stream() -> None:
    assert set(STREAM_FOR_EVENT) == set(EVENT_TYPES)


def test_every_stream_has_a_policy() -> None:
    assert set(POLICIES) == set(Stream)


def test_every_stream_is_bounded() -> None:
    """An unbounded stream is a memory-exhaustion outage waiting for the busiest
    hour of the event. The durable record lives in PostgreSQL."""
    for stream, policy in POLICIES.items():
        assert policy.max_length > 0, f"{stream} is unbounded"


def test_every_subscribed_stream_exists() -> None:
    for group, streams in SUBSCRIPTIONS.items():
        for stream in streams:
            assert stream in POLICIES, f"{group} subscribes to unknown stream {stream}"


def test_dead_letter_is_never_subscribed_to() -> None:
    """A poisoned message replayed automatically stalls the stream behind it.
    An operator decides, not a consumer."""
    for streams in SUBSCRIPTIONS.values():
        assert Stream.DEAD_LETTER not in streams


def test_rule_trigger_is_claimed_faster_than_telemetry() -> None:
    """Rule triggers feed alerting. A dead alert-engine replica's pending
    safety-critical triggers must be claimed by a peer in seconds, not half a
    minute."""
    assert (
        policy_for(Stream.RULE_TRIGGER).claim_min_idle_ms
        < policy_for(Stream.CAMERA_TICK).claim_min_idle_ms
    )


def test_rule_trigger_tolerates_more_deliveries_before_dead_lettering() -> None:
    assert (
        policy_for(Stream.RULE_TRIGGER).max_deliveries
        > policy_for(Stream.CAMERA_TICK).max_deliveries
    )


def test_alert_engine_consumes_rule_triggers_and_camera_health() -> None:
    from mansour_contracts.streams import ConsumerGroup

    subscribed = SUBSCRIPTIONS[ConsumerGroup.ALERT_ENGINE]
    assert Stream.RULE_TRIGGER in subscribed
    assert Stream.CAMERA_HEALTH in subscribed


class TestSeverityOrdering:
    def test_emergency_outranks_everything(self) -> None:
        assert Severity.INFO < Severity.WARNING < Severity.CRITICAL < Severity.EMERGENCY

    def test_ranking_is_usable_for_sorting(self) -> None:
        ordered = sorted([Severity.CRITICAL, Severity.INFO, Severity.EMERGENCY, Severity.WARNING])
        assert ordered == [
            Severity.INFO,
            Severity.WARNING,
            Severity.CRITICAL,
            Severity.EMERGENCY,
        ]

    def test_comparison_with_a_non_severity_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            _ = Severity.INFO < 1  # type: ignore[operator]
