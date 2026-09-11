"""The event contract (ADR 0007).

Five event types cross the spine. Each is **already aggregated** by the producing
`vision-worker`; no per-object detection is ever published. At 40 cameras this is
the difference between ~200 messages/second and ~12,000, and every one of those
200 is something a consumer reads.

Two invariants are enforced here, in the type system, rather than in prose:

1. **No person is identifiable.** There is no `track_id` field on any event, and
   `tests/test_privacy_invariants.py` fails the build if one ever appears. Track
   identifiers are the mechanism by which a crossing is *decided*; they are not
   part of the crossing that gets *published* (ADR 0004 §2).

2. **Every event is idempotent.** `event_id` is a deterministic function of the
   event's identity — its type, producer, scope, and time bucket — never of the
   moment it happened to be constructed. ADR 0007 gives at-least-once delivery,
   so a redelivered event must collide with the original on insert and be
   absorbed. Consumers upsert; they do not insert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mansour_common.clock import to_utc
from mansour_common.ids import deterministic_id
from mansour_contracts.enums import (
    CameraState,
    DensityLevel,
    DetectionClass,
    Direction,
    Severity,
)

#: Bumped when a field is removed or its meaning changes. Additive changes do not
#: bump it: consumers ignore unknown fields, producers never rely on that.
SCHEMA_VERSION = 1

ClassCounts = dict[DetectionClass, int]

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegative = Annotated[float, Field(ge=0.0)]


class Envelope(BaseModel):
    """Fields present on every event on the spine."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)

    event_id: UUID
    event_type: str
    schema_version: int = SCHEMA_VERSION

    #: When the observation was made, not when the message was serialised.
    occurred_at: datetime
    #: The worker or service instance that produced this event.
    producer: str = Field(min_length=1, max_length=128)
    #: Ties an event back to the incident or request that provoked it, if any.
    correlation_id: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def _must_be_utc_aware(cls, value: datetime) -> datetime:
        """Naive timestamps are ambiguous, and an ambiguous timestamp in an
        evidence manifest is worthless (Operational SRS ADM-006)."""
        return to_utc(value)


def _bucket(occurred_at: datetime) -> int:
    """Second-resolution time bucket.

    The tick events are emitted at 1 Hz, so the second is their natural identity.
    Two ticks for the same camera in the same second are the same tick, however
    many times the spine delivers them.
    """
    return int(occurred_at.timestamp())


class CameraTick(Envelope):
    """Per-camera aggregate, 1 Hz. The specification's `detections`, summarised."""

    event_type: Literal["camera.tick"] = "camera.tick"

    camera_id: UUID
    class_counts: ClassCounts = Field(default_factory=dict)
    person_count: int = Field(ge=0)
    density_level: DensityLevel

    #: Rate at which frames are actually analysed, not the camera's native rate.
    #: A camera streaming at 25 fps but analysed at 1 fps is blind to a horse at
    #: 15 m/s, and the dashboard must be able to say so (`CAM-004`).
    analytic_fps: NonNegative
    latency_ms: NonNegative
    inference_ms: NonNegative
    #: Rolling mean detection confidence. A sustained collapse means the camera
    #: can no longer see — nightfall, dust, a dirty lens (`CAM-011`).
    mean_confidence: Confidence | None = None

    @classmethod
    def create(
        cls, *, producer: str, occurred_at: datetime, camera_id: UUID, **fields: object
    ) -> CameraTick:
        occurred_at = to_utc(occurred_at)
        return cls(
            event_id=deterministic_id("camera.tick", str(camera_id), _bucket(occurred_at)),
            occurred_at=occurred_at,
            producer=producer,
            camera_id=camera_id,
            **fields,  # type: ignore[arg-type]
        )


class ZoneTick(Envelope):
    """Per-zone aggregate, 1 Hz."""

    event_type: Literal["zone.tick"] = "zone.tick"

    zone_id: UUID
    class_counts: ClassCounts = Field(default_factory=dict)
    occupancy_estimate: int = Field(ge=0)

    #: An occupancy figure with no error bar is a liability in a crowd-safety
    #: product (ADR 0006). Both of the next two fields are mandatory.
    occupancy_confidence: Confidence
    #: Seconds since occupancy was last re-anchored to a direct density estimate.
    #: The dashboard renders a stale estimate differently from a fresh one.
    anchor_age_seconds: NonNegative

    density_level: DensityLevel
    #: Persons per square metre. `None` when the contributing cameras are
    #: uncalibrated — never a plausible-looking substitute (Detection SRS §4.1).
    density_per_sqm: NonNegative | None = None

    @classmethod
    def create(
        cls, *, producer: str, occurred_at: datetime, zone_id: UUID, **fields: object
    ) -> ZoneTick:
        occurred_at = to_utc(occurred_at)
        return cls(
            event_id=deterministic_id("zone.tick", str(zone_id), _bucket(occurred_at)),
            occurred_at=occurred_at,
            producer=producer,
            zone_id=zone_id,
            **fields,  # type: ignore[arg-type]
        )


class CrossingEvent(Envelope):
    """A directional line crossing.

    Deliberately carries **no track identifier**. The track that produced this
    crossing died inside the worker, unpublished and unpersisted (ADR 0004).

    Because there is no track id, the event's identity is its
    `(line, class, direction, sequence)` — the worker supplies a monotonically
    increasing per-line sequence number so that two people crossing the same line
    in the same direction in the same second remain two events.
    """

    event_type: Literal["crossing.event"] = "crossing.event"

    camera_id: UUID
    line_id: UUID
    zone_id: UUID | None = None
    detection_class: DetectionClass
    direction: Direction
    #: Monotonic per-line counter. Makes the event id deterministic without a
    #: track id, and lets a consumer detect a gap caused by worker restart.
    sequence: int = Field(ge=0)

    @classmethod
    def create(
        cls, *, producer: str, occurred_at: datetime, line_id: UUID, sequence: int, **fields: object
    ) -> CrossingEvent:
        occurred_at = to_utc(occurred_at)
        return cls(
            event_id=deterministic_id("crossing.event", str(line_id), sequence),
            occurred_at=occurred_at,
            producer=producer,
            line_id=line_id,
            sequence=sequence,
            **fields,  # type: ignore[arg-type]
        )


class CameraHealth(Envelope):
    """Camera health transition, plus a 10-second heartbeat.

    `last_frame_age_seconds` is the field that matters. Camera-offline is keyed
    on frame staleness, not on whether the capture handle looks open: a dead
    network stream leaves `read()` blocking for tens of seconds while the handle
    still appears healthy.
    """

    event_type: Literal["camera.health"] = "camera.health"

    camera_id: UUID
    state: CameraState
    last_frame_age_seconds: NonNegative
    decode_errors: int = Field(default=0, ge=0)
    reconnect_count: int = Field(default=0, ge=0)
    #: False when this camera has no valid homography. Gates every ground-plane
    #: metric and suppresses crush-risk alerting (`CAL-005`).
    calibration_valid: bool = False
    #: Sequence number, so a heartbeat is idempotent within its emission window.
    sequence: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        *,
        producer: str,
        occurred_at: datetime,
        camera_id: UUID,
        sequence: int,
        **fields: object,
    ) -> CameraHealth:
        occurred_at = to_utc(occurred_at)
        return cls(
            event_id=deterministic_id("camera.health", str(camera_id), sequence),
            occurred_at=occurred_at,
            producer=producer,
            camera_id=camera_id,
            sequence=sequence,
            **fields,  # type: ignore[arg-type]
        )


class RuleTrigger(Envelope):
    """A zone or line predicate was satisfied. Feeds `alert-engine`.

    This is not an alert. It is the observation from which the alert engine may
    raise one, subject to cooldown, arming, and clustering. The distinction is
    the reason the worker does not need to know about cooldowns at all.
    """

    event_type: Literal["rule.trigger"] = "rule.trigger"

    rule: str = Field(min_length=1, max_length=64)
    severity: Severity
    camera_id: UUID | None = None
    zone_id: UUID | None = None

    #: The scope over which this rule's cooldown applies — a zone, a camera, a
    #: line. Generalises the prototype's per-object cooldown key.
    scope_key: str = Field(min_length=1, max_length=128)

    #: `(rule, scope_key, cooldown_window)`. Uniquely indexed downstream, which
    #: is how at-least-once delivery is made idempotent: a redelivered trigger
    #: hits the constraint and is absorbed.
    dedup_key: str = Field(min_length=1, max_length=256)

    #: The configuration version in force when this fired. Six months later
    #: someone will ask what the threshold was (Operational SRS §2.5).
    config_version: int = Field(ge=0)

    context: dict[str, float | int | str | bool] = Field(default_factory=dict)

    @classmethod
    def create(
        cls, *, producer: str, occurred_at: datetime, dedup_key: str, **fields: object
    ) -> RuleTrigger:
        occurred_at = to_utc(occurred_at)
        return cls(
            event_id=deterministic_id("rule.trigger", dedup_key),
            occurred_at=occurred_at,
            producer=producer,
            dedup_key=dedup_key,
            **fields,  # type: ignore[arg-type]
        )


#: Every event type on the spine. Consumers dispatch on `event_type`.
Event = CameraTick | ZoneTick | CrossingEvent | CameraHealth | RuleTrigger

EVENT_TYPES: dict[str, type[Envelope]] = {
    "camera.tick": CameraTick,
    "zone.tick": ZoneTick,
    "crossing.event": CrossingEvent,
    "camera.health": CameraHealth,
    "rule.trigger": RuleTrigger,
}


__all__ = [
    "EVENT_TYPES",
    "SCHEMA_VERSION",
    "CameraHealth",
    "CameraTick",
    "ClassCounts",
    "CrossingEvent",
    "Envelope",
    "Event",
    "RuleTrigger",
    "ZoneTick",
]
