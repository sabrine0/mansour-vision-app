"""The event contract: idempotency, UTC discipline, and closed vocabularies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mansour_contracts.enums import CameraState, DensityLevel, DetectionClass, Direction, Severity
from mansour_contracts.events import (
    EVENT_TYPES,
    SCHEMA_VERSION,
    CameraHealth,
    CameraTick,
    CrossingEvent,
    RuleTrigger,
    ZoneTick,
)

CAMERA = uuid4()
ZONE = uuid4()
LINE = uuid4()
AT = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)


def _tick(**overrides: object) -> CameraTick:
    fields: dict[str, object] = {
        "person_count": 3,
        "density_level": DensityLevel.NORMAL,
        "analytic_fps": 10.0,
        "latency_ms": 80.0,
        "inference_ms": 12.0,
    }
    fields.update(overrides)
    return CameraTick.create(producer="worker-1", occurred_at=AT, camera_id=CAMERA, **fields)


class TestIdempotency:
    def test_same_camera_and_second_yields_the_same_event_id(self) -> None:
        """ADR 0007 is at-least-once. A redelivered tick must collide on insert."""
        assert _tick().event_id == _tick(person_count=99).event_id

    def test_sub_second_jitter_does_not_change_the_event_id(self) -> None:
        jittered = CameraTick.create(
            producer="worker-1",
            occurred_at=AT + timedelta(milliseconds=400),
            camera_id=CAMERA,
            person_count=3,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=80.0,
            inference_ms=12.0,
        )
        assert jittered.event_id == _tick().event_id

    def test_different_second_yields_a_different_event_id(self) -> None:
        later = CameraTick.create(
            producer="worker-1",
            occurred_at=AT + timedelta(seconds=1),
            camera_id=CAMERA,
            person_count=3,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=80.0,
            inference_ms=12.0,
        )
        assert later.event_id != _tick().event_id

    def test_different_camera_yields_a_different_event_id(self) -> None:
        other = CameraTick.create(
            producer="worker-1",
            occurred_at=AT,
            camera_id=uuid4(),
            person_count=3,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=80.0,
            inference_ms=12.0,
        )
        assert other.event_id != _tick().event_id

    def test_producer_does_not_affect_event_identity(self) -> None:
        """The same observation re-emitted by a restarted worker is the same
        observation. Identity is the tick, not who happened to publish it."""
        other = CameraTick.create(
            producer="worker-2",
            occurred_at=AT,
            camera_id=CAMERA,
            person_count=3,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=80.0,
            inference_ms=12.0,
        )
        assert other.event_id == _tick().event_id

    def test_crossings_in_the_same_second_remain_distinct(self) -> None:
        """Two people cross the same line in the same direction in one second.
        Without a track id, the per-line sequence is what keeps them apart."""
        first = CrossingEvent.create(
            producer="worker-1",
            occurred_at=AT,
            line_id=LINE,
            sequence=41,
            camera_id=CAMERA,
            detection_class=DetectionClass.PERSON,
            direction=Direction.IN,
        )
        second = CrossingEvent.create(
            producer="worker-1",
            occurred_at=AT,
            line_id=LINE,
            sequence=42,
            camera_id=CAMERA,
            detection_class=DetectionClass.PERSON,
            direction=Direction.IN,
        )
        assert first.event_id != second.event_id

    def test_rule_trigger_identity_is_its_dedup_key(self) -> None:
        def trigger(dedup: str) -> RuleTrigger:
            return RuleTrigger.create(
                producer="worker-1",
                occurred_at=AT,
                dedup_key=dedup,
                rule="HIGH_DENSITY",
                severity=Severity.WARNING,
                scope_key=f"zone:{ZONE}",
                config_version=7,
            )

        assert trigger("HIGH_DENSITY|zone:x|1752") == trigger("HIGH_DENSITY|zone:x|1752")
        assert trigger("HIGH_DENSITY|zone:x|1752") != trigger("HIGH_DENSITY|zone:x|1753")


class TestTimestamps:
    def test_naive_occurred_at_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="naive datetime rejected"):
            CameraTick(
                event_id=uuid4(),
                occurred_at=datetime(2026, 7, 9, 12, 0),  # noqa: DTZ001 — the point of the test
                producer="worker-1",
                camera_id=CAMERA,
                person_count=0,
                density_level=DensityLevel.NORMAL,
                analytic_fps=10.0,
                latency_ms=1.0,
                inference_ms=1.0,
            )

    def test_offset_timestamps_are_normalised_to_utc(self) -> None:
        casablanca = timezone(timedelta(hours=1))
        tick = CameraTick.create(
            producer="worker-1",
            occurred_at=datetime(2026, 7, 9, 13, 0, tzinfo=casablanca),
            camera_id=CAMERA,
            person_count=0,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=1.0,
            inference_ms=1.0,
        )
        assert tick.occurred_at.utcoffset() == timedelta(0)
        assert tick.occurred_at.hour == 12

    def test_an_offset_timestamp_has_the_same_identity_as_its_utc_equivalent(self) -> None:
        casablanca = timezone(timedelta(hours=1))
        local = CameraTick.create(
            producer="w",
            occurred_at=datetime(2026, 7, 9, 13, 0, tzinfo=casablanca),
            camera_id=CAMERA,
            person_count=0,
            density_level=DensityLevel.NORMAL,
            analytic_fps=10.0,
            latency_ms=1.0,
            inference_ms=1.0,
        )
        assert local.event_id == _tick(person_count=0).event_id


class TestValidation:
    def test_events_are_frozen(self) -> None:
        tick = _tick()
        with pytest.raises(ValidationError):
            tick.person_count = 99  # type: ignore[misc]

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _tick(track_id=17)

    def test_negative_person_count_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _tick(person_count=-1)

    def test_unknown_detection_class_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CrossingEvent.create(
                producer="w",
                occurred_at=AT,
                line_id=LINE,
                sequence=0,
                camera_id=CAMERA,
                detection_class="camel",
                direction=Direction.IN,
            )

    def test_confidence_is_bounded(self) -> None:
        with pytest.raises(ValidationError):
            _tick(mean_confidence=1.5)

    def test_zone_tick_requires_occupancy_confidence(self) -> None:
        """An occupancy figure with no error bar is a liability (ADR 0006)."""
        with pytest.raises(ValidationError):
            ZoneTick.create(
                producer="w",
                occurred_at=AT,
                zone_id=ZONE,
                occupancy_estimate=120,
                anchor_age_seconds=4.0,
                density_level=DensityLevel.ELEVATED,
            )

    def test_uncalibrated_zone_reports_no_density_value(self) -> None:
        """`density_per_sqm` is optional precisely so an uncalibrated camera can
        decline to answer, rather than emit a plausible-looking number."""
        tick = ZoneTick.create(
            producer="w",
            occurred_at=AT,
            zone_id=ZONE,
            occupancy_estimate=120,
            occupancy_confidence=0.4,
            anchor_age_seconds=90.0,
            density_level=DensityLevel.UNCALIBRATED,
        )
        assert tick.density_per_sqm is None


class TestSchemaSurface:
    def test_every_event_type_is_registered(self) -> None:
        assert set(EVENT_TYPES) == {
            "camera.tick",
            "zone.tick",
            "crossing.event",
            "camera.health",
            "rule.trigger",
        }

    @pytest.mark.parametrize("event_type", sorted(EVENT_TYPES))
    def test_event_type_literal_matches_its_registry_key(self, event_type: str) -> None:
        model = EVENT_TYPES[event_type]
        assert model.model_fields["event_type"].default == event_type

    @pytest.mark.parametrize("event_type", sorted(EVENT_TYPES))
    def test_schema_version_is_stamped(self, event_type: str) -> None:
        assert EVENT_TYPES[event_type].model_fields["schema_version"].default == SCHEMA_VERSION

    def test_round_trip_through_json(self) -> None:
        tick = _tick()
        assert CameraTick.model_validate_json(tick.model_dump_json()) == tick

    def test_camera_health_round_trip(self) -> None:
        health = CameraHealth.create(
            producer="worker-1",
            occurred_at=AT,
            camera_id=CAMERA,
            sequence=3,
            state=CameraState.OFFLINE,
            last_frame_age_seconds=12.5,
        )
        assert CameraHealth.model_validate_json(health.model_dump_json()) == health
        assert health.calibration_valid is False, "calibration must default to invalid"
