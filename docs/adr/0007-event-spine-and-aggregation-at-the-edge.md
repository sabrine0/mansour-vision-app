# ADR 0007 — Redis Streams as the event spine; aggregate at the worker

**Status:** Accepted
**Date:** 2026-07-09

## Context

The prototype runs detection, alert evaluation, per-minute aggregation, and
SQLite writes inside one process, on one 1 Hz tick. At one camera this is
correct and simple. At forty cameras it fails in three independent ways: a slow
database write stalls detection; a detector crash takes the API down; and there
is no way to add a consumer (say, a reporting pipeline) without touching the
detector.

The naive distributed version fails differently. If each worker emitted one
message per detected object per frame:

```
40 cameras × 10 analytic FPS × ~30 objects = 12,000 messages/second
```

— of which essentially none carry information the dashboard can use. The
dashboard displays *counts*, not boxes. Publishing raw per-object detections
would build a firehose to transport data nobody consumes, and it would put
bounding boxes of people onto a durable, replayable bus, which sits badly with
ADR 0004.

## Decision

**Redis Streams is the event spine.** It gives durable, ordered, replayable
streams with consumer groups and at-least-once delivery, without operating
Kafka. If throughput ever demands it, the consumer-group semantics port to Kafka
with a contained change; nothing in the domain code assumes Redis.

**Workers aggregate before they publish.** A `vision-worker` never emits a raw
per-object detection. It emits five event types, all already summarized:

| Event | Rate | Payload (essentials) |
|---|---|---|
| `camera.tick` | 1 Hz per camera | per-class counts in frame, density level, fps, latency |
| `zone.tick` | 1 Hz per zone | occupancy estimate, per-class counts inside the polygon |
| `crossing.event` | on crossing | camera, line, class, direction — **no track id** |
| `camera.health` | on change + 10 s heartbeat | state, last frame age, decode errors |
| `rule.trigger` | on condition | zone predicate satisfied (feeds `alert-engine`) |

Total steady-state volume at 40 cameras: **under 200 messages/second**, two
orders of magnitude below the naive design, and every message is something a
consumer actually reads.

Track IDs terminate inside the worker process. They are the mechanism by which a
crossing is decided; they are not part of the crossing that gets published
(ADR 0004 §2).

## Consequences

- Failure domains separate cleanly. The database can be slow, the alert engine
  can restart, a consumer can be added — and detection keeps running, because
  detection's only downstream obligation is `XADD` to a stream.
- Streams are replayable, so `analytics-consumer` can be rebuilt from history,
  and a new aggregation can be backfilled without re-running inference.
- Retention on the streams is bounded (`MAXLEN ~`), because the durable record of
  the day lives in PostgreSQL/TimescaleDB, not in Redis.
- **The cost:** the worker now owns zone geometry, because it must evaluate
  "which polygon is this box inside" before it can aggregate. Zone definitions
  are therefore pushed *to* workers by `core-api` and cached, and a zone edit
  must propagate to workers within seconds. This is the main complexity this ADR
  introduces, and it is the price of not building a firehose.
- At-least-once delivery means consumers must be **idempotent**. Every event
  carries a deterministic `event_id`; `analytics-consumer` upserts rather than
  inserts. Alerts are deduplicated on `(rule, scope_key, cooldown_window)` — the
  prototype's per-scope cooldown design (`alerts.py`) already has the right shape
  and generalizes to this directly.
