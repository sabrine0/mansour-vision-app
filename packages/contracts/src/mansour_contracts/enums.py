"""Closed vocabularies shared by every producer and consumer.

These are the only values the platform recognises. A new detection class, alert
severity, or camera state is a contract change with a schema version bump — not
a string somebody typed into a config file.
"""

from __future__ import annotations

from enum import StrEnum


class DetectionClass(StrEnum):
    """What the detector may emit.

    Exactly the pretrained COCO classes named in ADR 0003. Everything else the
    specification asks for is either a configured zone polygon, or a rule over
    these, or a deferred custom-model item. Adding a member here without a model
    that produces it would be a lie in the type system.
    """

    PERSON = "person"
    HORSE = "horse"
    DOG = "dog"
    CAR = "car"
    TRUCK = "truck"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"


#: Classes that participate in vehicle rules (`VEH-011` vehicle-in-pedestrian-zone).
VEHICLE_CLASSES: frozenset[DetectionClass] = frozenset(
    {
        DetectionClass.CAR,
        DetectionClass.TRUCK,
        DetectionClass.BUS,
        DetectionClass.MOTORCYCLE,
        DetectionClass.BICYCLE,
    }
)


class DensityLevel(StrEnum):
    """Fruin Level-of-Service bands (Detection SRS §4.1).

    `UNCALIBRATED` is not a band. It is the assertion that this camera cannot
    express density in persons/m² and therefore has no opinion. It must never be
    rendered as a colour, and it must never satisfy a crush-risk rule. A number
    that looks authoritative and means nothing is the prohibited failure mode.
    """

    UNCALIBRATED = "uncalibrated"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class Direction(StrEnum):
    """Line-crossing polarity. Declared per line, never inferred from endpoint order."""

    IN = "in"
    OUT = "out"


class Severity(StrEnum):
    """Alert severity (Operational SRS §10).

    `EMERGENCY` is never suppressed, never batched, never subject to quiet hours,
    and never disarmed by a schedule. That is enforced downstream; the ordering
    here is what makes it checkable.
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
    Severity.EMERGENCY: 3,
}


class CameraState(StrEnum):
    """Observed camera state.

    `UNKNOWN` exists because `HRS-007` requires that the absence of an
    observation never be reported as a good one. A camera whose state we cannot
    establish is `UNKNOWN`, never `ONLINE`.
    """

    UNKNOWN = "unknown"
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    TAMPERED = "tampered"
    MAINTENANCE = "maintenance"


class TrackState(StrEnum):
    """Charge-track state machine (`HRS-005`).

    Drives incursion severity and the contextual arming of the smoke rule.
    `UNKNOWN` is the safe default: it forces `no-go` rather than `clear`.
    """

    UNKNOWN = "unknown"
    CLEARED = "cleared"
    STAGED = "staged"
    CHARGING = "charging"


__all__ = [
    "VEHICLE_CLASSES",
    "CameraState",
    "DensityLevel",
    "DetectionClass",
    "Direction",
    "Severity",
    "TrackState",
]
