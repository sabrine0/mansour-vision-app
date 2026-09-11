# ADR 0003 — Static infrastructure is configuration, not detection

**Status:** Accepted
**Date:** 2026-07-09

## Context

The product specification lists as *detection classes*: Main Entrance, Gate,
Emergency Exit, Parking Entrance, Restricted Area, Horse Arena, Horse Waiting
Area, Waiting Area, Medical Tent, Security Checkpoint, Barrier, Fence.

These are not objects to be recognized. They are **fixed locations in a fixed
camera's field of view.** A gate does not move between frames. Training a neural
network to rediscover, thirty times a second, where the emergency exit is — when
the exit has not moved since the venue was built — is both wasteful and *less
reliable* than an operator drawing a polygon around it once.

The specification's alert list makes this unavoidable. "Emergency Exit Blocked"
cannot be a detection; there is no visual class `blocked_emergency_exit`. It is
necessarily a spatial predicate: *a detected object of a certain class, inside a
known region, for longer than a threshold.*

## Decision

The world model splits in two.

**Detected (per frame, by the model):** only things that move and that a
pretrained COCO model already knows — `person`, `horse`, `dog`, `car`,
`motorcycle`, `bus`, `truck`, `bicycle`.

**Configured (once, by an operator):** every static feature, as a named
**Zone** — a polygon in normalized image coordinates, optionally with GPS
corners, a capacity, and a risk level. Zones have a `kind`
(`entrance`, `exit`, `emergency_exit`, `parking`, `restricted`, `arena`,
`waiting`, `medical`, `checkpoint`, `pedestrian_only`, …).

**Derived (by rules over the two):** every alert in the specification.

| Specified alert | Implementation |
|---|---|
| Emergency Exit Blocked | any object inside `kind=emergency_exit` for > N s |
| Restricted Area Occupied | any `person`/`vehicle` inside `kind=restricted` |
| Vehicle in Pedestrian Zone | vehicle class inside `kind=pedestrian_only` |
| Horse in Restricted Area | `horse` inside `kind=restricted` |
| Parking Full | occupancy of `kind=parking` ≥ its configured capacity |
| Blocked Entrance / Exit | occupancy high **and** throughput ≈ 0 across its line |
| Queue Too Long | occupancy of `kind=waiting` ≥ threshold |

## Compositional classes

Two requested "classes" are relations between two detected boxes, not classes.
They are computed as rules and require **no training**:

- **Horse Rider** — a `person` box whose lower centroid lies inside a `horse`
  box, sustained across ≥ 3 consecutive tracked frames.
- **Multiple Horses / Groups / Crowd** — a count predicate over detections
  within a zone, not a distinct visual entity.

## Explicitly deferred to R&D

`tent`, `market_stall`, `food_stall`, `horse_trailer`, `ambulance`,
`fire_truck`, `police_vehicle` have no pretrained equivalent and require a
labeled dataset from the target event. Emergency-vehicle *type* in particular is
poorly separable visually (an ambulance is a van with livery); the reliable
signal is a dispatch-system integration or an operator marking, not a camera.
These are tracked in the custom-dataset backlog, not in v1.

## Consequences

- v1 ships with **zero custom model training** and still satisfies every alert
  in the specification except emergency-vehicle typing.
- Zone geometry becomes first-class in the data model, the API, and the UI. An
  operator-facing polygon editor over a live frame is now a required v1 feature,
  not a nice-to-have. This is real frontend work and is budgeted.
- Alert quality now depends on *operator configuration accuracy*, which is a
  training and UX problem rather than an ML problem. That is a much better place
  for the risk to sit: a wrong polygon is visible and fixable in seconds; a
  mistrained class is neither.
- Zones are per-camera geometry **and** per-venue semantics. A single logical
  zone ("Parking North") may be observed by several cameras, each contributing
  its own polygon. The data model must therefore separate `Zone` (semantic,
  venue-level) from `CameraZone` (geometric, camera-level).
