"""Identifier generation.

Two kinds of identifier, for two different jobs.

**Deterministic ids** (`deterministic_id`) make consumers idempotent. ADR 0007
gives at-least-once delivery on the event spine, so the same `camera.tick` may
arrive twice. If its `event_id` is a function of its content and scope rather
than of the moment it was generated, a redelivery collides with the original on
insert and is absorbed. The producer does not need to remember anything.

**Random ids** (`new_id`) label things that genuinely are new each time: a
request, an incident, an alert instance.

Neither is ever derived from, or attached to, a person. Track identifiers do not
appear in this module because they never leave the worker process (ADR 0004).
"""

from __future__ import annotations

import uuid

#: Stable namespace for all deterministic ids in the platform. Changing this
#: value would silently break idempotency across a deployment boundary, so it is
#: a constant and not configuration.
NAMESPACE = uuid.UUID("6f3a2b18-9c5e-5d41-8a7f-1e0c4b2d9f63")


def new_id() -> uuid.UUID:
    """A fresh random identifier (UUIDv4)."""
    return uuid.uuid4()


def deterministic_id(*parts: str | int) -> uuid.UUID:
    """Derive a stable UUIDv5 from the given parts.

    Parts are length-prefixed rather than joined by a separator. Any separator,
    however exotic, can appear inside a part — a camera name, a zone name — and
    then `("a|", "b")` and `("a", "|b")` would hash identically, silently fusing
    two distinct events into one id. Length-prefixing is injective for every
    input, which is the property idempotency actually depends on.
    """
    if not parts:
        raise ValueError("deterministic_id requires at least one part")
    encoded = "".join(f"{len(s)}:{s}" for s in (str(p) for p in parts))
    return uuid.uuid5(NAMESPACE, encoded)


def correlation_id() -> str:
    """A short, log-friendly correlation identifier."""
    return uuid.uuid4().hex


__all__ = ["NAMESPACE", "correlation_id", "deterministic_id", "new_id"]
