"""ADR 0004, enforced by the build.

The privacy guarantee is architectural, not advisory. These tests are the
mechanism: they inspect every event schema the platform can emit and fail if a
field appears that could identify, track, or characterise a person.

If a future change makes one of these fail, the correct response is to remove the
field — not to amend the test. The refusal is the product.
"""

from __future__ import annotations

import pytest

from mansour_contracts.events import EVENT_TYPES

#: Field names that would breach ADR 0004 if published on the spine.
#: `track_id` is the realistic one: it is genuinely useful inside the worker, and
#: publishing it is a single careless line away.
FORBIDDEN_FIELDS = frozenset(
    {
        "track_id",
        "track_ids",
        "person_id",
        "identity",
        "embedding",
        "embeddings",
        "face",
        "face_id",
        "descriptor",
        "feature_vector",
        "reid",
        "re_id",
        "age",
        "age_band",
        "gender",
        "sex",
        "ethnicity",
        "race",
        "plate",
        "license_plate",
        "plate_number",
        "biometric",
        "gait",
        "emotion",
    }
)

#: Substrings that betray an identifying field under a different name.
FORBIDDEN_SUBSTRINGS = ("biometric", "faceprint", "reidentif", "re_identif")


@pytest.mark.parametrize("event_type", sorted(EVENT_TYPES))
def test_no_event_publishes_an_identifying_field(event_type: str) -> None:
    model = EVENT_TYPES[event_type]
    fields = set(model.model_fields)

    breach = fields & FORBIDDEN_FIELDS
    assert not breach, (
        f"{event_type} publishes {sorted(breach)}, which breaches ADR 0004. "
        "Remove the field. Do not amend this test."
    )


@pytest.mark.parametrize("event_type", sorted(EVENT_TYPES))
def test_no_event_field_name_suggests_identification(event_type: str) -> None:
    model = EVENT_TYPES[event_type]

    for name in model.model_fields:
        lowered = name.lower()
        for needle in FORBIDDEN_SUBSTRINGS:
            assert needle not in lowered, (
                f"{event_type}.{name} suggests identification of a person (ADR 0004)."
            )


@pytest.mark.parametrize("event_type", sorted(EVENT_TYPES))
def test_serialised_schema_contains_no_identifying_property(event_type: str) -> None:
    """Belt and braces: inspect the emitted JSON Schema, not just the model.

    A nested model, an alias, or a `model_config` alias generator could smuggle a
    field past the `model_fields` check above. The schema is what actually
    crosses the wire.
    """
    schema = EVENT_TYPES[event_type].model_json_schema(mode="serialization")
    serialised = str(schema).lower()

    for forbidden in FORBIDDEN_FIELDS:
        assert f"'{forbidden}'" not in serialised, (
            f"{event_type}'s JSON Schema mentions {forbidden!r} (ADR 0004)."
        )


def test_crossing_event_carries_no_track_identity() -> None:
    """The specific case the architecture is designed around.

    A crossing is decided from a track's centroid history. The track is the
    mechanism; it is not the event. It dies inside the worker.
    """
    fields = set(EVENT_TYPES["crossing.event"].model_fields)

    assert "track_id" not in fields
    assert "sequence" in fields, (
        "crossing identity must come from a per-line sequence number, not from a track identifier"
    )
