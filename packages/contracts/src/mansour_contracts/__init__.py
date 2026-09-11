"""The event and stream contracts for MANSOUR Vision.

The single source of truth for what crosses the event spine. Producers and
consumers import from here; the TypeScript dashboard consumes types generated
from `mansour_contracts.export`.
"""

from __future__ import annotations

__version__ = "0.1.0"

from mansour_contracts.enums import (
    VEHICLE_CLASSES,
    CameraState,
    DensityLevel,
    DetectionClass,
    Direction,
    Severity,
    TrackState,
)
from mansour_contracts.events import (
    EVENT_TYPES,
    SCHEMA_VERSION,
    CameraHealth,
    CameraTick,
    CrossingEvent,
    Envelope,
    Event,
    RuleTrigger,
    ZoneTick,
)
from mansour_contracts.streams import (
    POLICIES,
    STREAM_FOR_EVENT,
    SUBSCRIPTIONS,
    ConsumerGroup,
    Stream,
    StreamPolicy,
)

__all__ = [
    "EVENT_TYPES",
    "POLICIES",
    "SCHEMA_VERSION",
    "STREAM_FOR_EVENT",
    "SUBSCRIPTIONS",
    "VEHICLE_CLASSES",
    "CameraHealth",
    "CameraState",
    "CameraTick",
    "ConsumerGroup",
    "CrossingEvent",
    "DensityLevel",
    "DetectionClass",
    "Direction",
    "Envelope",
    "Event",
    "RuleTrigger",
    "Severity",
    "Stream",
    "StreamPolicy",
    "TrackState",
    "ZoneTick",
    "__version__",
]
