# ADR 0006 — Dwell time by Little's Law; occupancy by reconciliation

**Status:** Accepted
**Date:** 2026-07-09
**Depends on:** ADR 0004 (no biometric inference)

## Context

Two requirements in the specification appear, at first reading, to contradict
ADR 0004:

- **Average Stay** and **Waiting Time** — how long people remain in a zone.
- **Live Occupancy** and **Historical Occupancy** — how many people are in a zone.

The naive implementation of the first is to follow each individual from entry to
exit and subtract timestamps. Within one camera that is merely tracking; across
cameras it is **re-identification**, which ADR 0004 prohibits at the
architectural level. We need these metrics without it.

The naive implementation of the second is `occupancy = Σ crossings_in − Σ crossings_out`.
This is worse than it looks. It is an *unbounded integrator of error*: every
missed or double-counted crossing is added to the estimate permanently. A counter
that is 99% accurate on a gate seeing 20,000 people will be off by hundreds by
evening, and it will never self-correct. Operators lose trust in the number, and
a crowd-safety product whose crowd number is not trusted has no reason to exist.

## Decision

### Dwell time comes from Little's Law

For any queueing system in steady state:

```
L = λ · W        ⟹        W = L / λ
```

where `L` is mean occupancy, `λ` is the mean arrival rate, and `W` is the mean
time an entity spends in the system. Both `L` and `λ` are quantities we already
measure — occupancy from density estimation, arrival rate from line crossings.

Therefore **average stay and waiting time are computed from two aggregate
numbers, and require following no one.** No person is tracked from entry to exit.
No identity, ephemeral or otherwise, spans the measurement.

Applicability and its limits, stated honestly:

- It yields a **mean over a population in a window**, not a per-person duration.
  This is what an operator needs ("the north gate queue is running eight
  minutes") and is strictly less information than a per-person figure — which is
  the point.
- It assumes approximate steady state over the averaging window. We use a
  10-minute sliding window and **suppress the metric** when `λ` is near zero or
  when occupancy is changing faster than the window can absorb, rather than
  reporting a confident wrong number. A suppressed metric renders as "—", never
  as `0`.
- It is exact in the long run for any arrival process, which is stronger than it
  first appears — it needs no Poisson assumption.

### Occupancy is reconciled, never integrated indefinitely

Occupancy for a zone is maintained as a **counting estimate that is periodically
corrected against a direct observation**:

1. Between corrections, occupancy advances by net line crossings (high temporal
   resolution, drifts).
2. At intervals, and whenever cameras have adequate coverage of the zone,
   occupancy is **re-anchored** to the direct density estimate — the count of
   distinct person detections inside the zone polygons, de-duplicated across
   overlapping camera views by polygon geometry, never by appearance matching
   (which would be re-identification).
3. Zones known to be empty — before doors open, after the venue clears — are
   **hard-reset to zero**, and the residual is logged as the day's accumulated
   counting error. That residual is a first-class quality metric, exposed in the
   system-health view. It is how we know whether to trust the gate.
4. Every occupancy value carries a **confidence** and the **age of its last
   anchor**. The dashboard renders a stale estimate differently from a fresh one.

## Consequences

- The two metrics the specification wanted are delivered, and the privacy
  guarantee in ADR 0004 survives intact. This is a stronger sales position than
  a competitor's per-individual dwell time, not a weaker one.
- Counting accuracy becomes *observable*: the end-of-day reconciliation residual
  tells us, per gate, how good the line counting actually is. Most systems in
  this class never find out.
- `analytics-consumer` owns this logic. It is deliberately not in the
  `vision-worker`: reconciliation needs a venue-wide view across cameras, and the
  worker must never block on cross-camera state.
- We must build de-duplication of overlapping camera coverage from geometry
  (homography of zone polygons to a venue ground plane). This is real work and is
  the main cost of this ADR. It is also the only privacy-preserving way to do it.
