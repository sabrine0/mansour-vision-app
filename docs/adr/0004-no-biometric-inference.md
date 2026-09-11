# ADR 0004 — No biometric inference, no exceptions

**Status:** Accepted
**Date:** 2026-07-09

## Context

MANSOUR Vision's central claim is that it delivers operational awareness over
crowds **without identifying anyone**. That claim is the product's licence to
operate in public spaces and its principal differentiator against conventional
CCTV analytics.

A claim of this kind is only as strong as its weakest exception. The
specification's prohibitions — no face recognition, no person identification, no
biometric recognition, no identity tracking, no license plate recognition, no
personal profiling — were undermined by a single line elsewhere in the same
document: `PERSON: Adult, Child (optional)`.

Classifying a detected person as a child is an inference of a **special-category
personal attribute** (age band) about a **minor**, from **bodily appearance**.
Under GDPR Art. 9 reasoning and the EU AI Act's treatment of biometric
categorisation, that is biometric categorisation regardless of whether a face is
processed or an identity is resolved. It is precisely the thing the other six
prohibitions promise not to do.

The operational need it likely encodes — *find a lost child* — does not actually
require knowing that anyone is a child.

## Decision

**The platform performs no inference of any personal attribute of any kind.**
The system may know that a pixel region is *a person*, where that person is, and
which direction they moved. It may not infer age, sex, gender, race, clothing
type, gait, emotional state, or identity, and it may not link an observation of
a person on one camera to an observation of a person on another camera.

Specifically:

1. **Child / age classification is removed** from the specification, the
   taxonomy, the roadmap, and all sales material. It is not deferred; it is
   abandoned.
2. **Track IDs are ephemeral, per-camera, and never persisted.** They exist
   inside a single `vision-worker` process, are reused freely, and are never
   written to the database or emitted on the event bus. A track ID is a frame-to-frame
   correspondence hint, not an identifier of a human being.
3. **No cross-camera association of persons.** Re-identification is prohibited
   at the architectural level: there is no component that receives person crops
   or embeddings from two cameras. See ADR 0006 for how dwell time is obtained
   without it.
4. **No person imagery is persisted** except a snapshot attached to a raised
   alert, which is retained under a configurable retention policy and is subject
   to audit logging on access.
5. **License plates are never read.** Vehicles are counted as boxes.

## The lost-child need, solved without age inference

The underlying operational requirement is met by a rule over anonymous geometry:
a *small-stature* detection (a bounding-box height percentile relative to other
persons in the same zone — a **relative** measure, never an absolute age claim),
which is **stationary** and **spatially isolated from crowd flow** for longer
than N minutes, raises a `POSSIBLE_LOST_PERSON` advisory for an operator to look
at with their own eyes.

The system asserts *"something at these coordinates warrants a human look."*
It never asserts *"this is a child."* The distinction is not cosmetic: the first
is a pointer, the second is a classification of a minor, and only the second
creates a legal obligation.

## Consequences

- The privacy claim becomes unqualified and therefore defensible. There is no
  "except…" to explain in a Data Protection Impact Assessment.
- The architecture *enforces* the policy rather than documenting it. A future
  engineer cannot quietly add re-identification, because no service is wired to
  carry the embeddings it would need.
- Some analytics that competitors advertise (demographic breakdowns, dwell time
  per individual) are permanently unavailable to us. This is the intended trade.
- Snapshot retention and access become auditable events (ADR series on security).
