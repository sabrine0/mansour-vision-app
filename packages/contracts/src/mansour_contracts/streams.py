"""Stream names, consumer groups, and retention on the event spine (ADR 0007).

Redis Streams gives durable, ordered, replayable streams with consumer groups
and at-least-once delivery, without operating Kafka. Nothing in the domain code
assumes Redis; these are the only Redis-shaped facts, and the consumer-group
semantics port to Kafka with a contained change.

Retention is bounded. The durable record of the day lives in
PostgreSQL/TimescaleDB, not in Redis. A stream that grows without limit is a
memory-exhaustion outage waiting for the busiest hour of the event.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Stream(StrEnum):
    """Physical stream names."""

    CAMERA_TICK = "mansour:camera.tick"
    ZONE_TICK = "mansour:zone.tick"
    CROSSING = "mansour:crossing.event"
    CAMERA_HEALTH = "mansour:camera.health"
    RULE_TRIGGER = "mansour:rule.trigger"
    #: Messages a consumer could not process. Never auto-replayed; an operator
    #: decides. A poisoned message that is retried forever stalls the stream
    #: behind it, which is worse than dropping it and saying so.
    DEAD_LETTER = "mansour:dead-letter"


class ConsumerGroup(StrEnum):
    """Consumer groups. One per service, per stream it reads."""

    ANALYTICS = "analytics-consumer"
    ALERT_ENGINE = "alert-engine"


@dataclass(frozen=True, slots=True)
class StreamPolicy:
    """Retention and delivery policy for one stream."""

    stream: Stream
    #: Approximate cap on stream length (`XADD ... MAXLEN ~ n`). Approximate
    #: trimming is dramatically cheaper and the slack is irrelevant here.
    max_length: int
    #: Milliseconds a message may remain pending before another consumer in the
    #: group may claim it. Sized to the consumer's realistic processing time.
    claim_min_idle_ms: int
    #: Deliveries after which a message is dead-lettered rather than retried.
    max_deliveries: int


#: At 40 cameras the tick streams carry ~40 msg/s. A 100k cap is ~40 minutes of
#: replay headroom — enough for a consumer restart, far short of a memory risk.
_TICK_CAP = 100_000

POLICIES: dict[Stream, StreamPolicy] = {
    Stream.CAMERA_TICK: StreamPolicy(Stream.CAMERA_TICK, _TICK_CAP, 30_000, 5),
    Stream.ZONE_TICK: StreamPolicy(Stream.ZONE_TICK, _TICK_CAP, 30_000, 5),
    Stream.CROSSING: StreamPolicy(Stream.CROSSING, 500_000, 30_000, 5),
    Stream.CAMERA_HEALTH: StreamPolicy(Stream.CAMERA_HEALTH, 50_000, 30_000, 5),
    # Rule triggers feed alerting. A shorter idle window means a dead alert-engine
    # replica's pending safety-critical triggers are claimed by a peer in seconds.
    Stream.RULE_TRIGGER: StreamPolicy(Stream.RULE_TRIGGER, 200_000, 5_000, 10),
    Stream.DEAD_LETTER: StreamPolicy(Stream.DEAD_LETTER, 50_000, 60_000, 1),
}

#: Which streams each consumer group reads.
SUBSCRIPTIONS: dict[ConsumerGroup, tuple[Stream, ...]] = {
    ConsumerGroup.ANALYTICS: (
        Stream.CAMERA_TICK,
        Stream.ZONE_TICK,
        Stream.CROSSING,
        Stream.CAMERA_HEALTH,
    ),
    ConsumerGroup.ALERT_ENGINE: (
        Stream.RULE_TRIGGER,
        Stream.CAMERA_HEALTH,
    ),
}

#: Event type -> the stream it is published to.
STREAM_FOR_EVENT: dict[str, Stream] = {
    "camera.tick": Stream.CAMERA_TICK,
    "zone.tick": Stream.ZONE_TICK,
    "crossing.event": Stream.CROSSING,
    "camera.health": Stream.CAMERA_HEALTH,
    "rule.trigger": Stream.RULE_TRIGGER,
}


def policy_for(stream: Stream) -> StreamPolicy:
    return POLICIES[stream]


__all__ = [
    "POLICIES",
    "STREAM_FOR_EVENT",
    "SUBSCRIPTIONS",
    "ConsumerGroup",
    "Stream",
    "StreamPolicy",
    "policy_for",
]
