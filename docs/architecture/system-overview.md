# MANSOUR Vision — System Overview

AI-powered event command & control. Anonymous operational monitoring of crowds,
traffic, horses, and venue infrastructure across an arbitrary number of cameras,
presented in a single command center.

> **What this system never does:** face recognition, person identification,
> biometric categorisation (including age), identity tracking, cross-camera
> re-identification, license plate recognition, personal profiling. This is
> enforced architecturally, not by policy. See [ADR 0004](../adr/0004-no-biometric-inference.md).

## Service topology

```
   RTSP / ONVIF / NVR / USB
             │
             ▼
   ┌──────────────────┐   camera.tick, zone.tick, crossing.event,
   │  vision-worker   │   camera.health, rule.trigger
   │  (N replicas,    │────────────────┐
   │   GPU-pinned)    │                │
   │                  │                ▼
   │  decode          │        ┌───────────────┐
   │  → RT-DETRv2     │        │ Redis Streams │  ◄── the event spine
   │  → ByteTrack     │        └───────┬───────┘
   │  → zone + line   │                │
   │  → AGGREGATE     │      ┌─────────┴──────────┐
   └────────┬─────────┘      ▼                    ▼
            │        ┌───────────────┐   ┌─────────────────┐
            │        │ alert-engine  │   │analytics-consumer│
            │        │ rules, cooldown│  │ aggregation,     │
            │        │ escalation     │  │ reconciliation,  │
            │        │ assignment     │  │ Little's Law     │
            │        └───────┬───────┘   └────────┬────────┘
            │                │                    │
            │                └────────┬───────────┘
            │                         ▼
            │              ┌─────────────────────┐
            │              │ PostgreSQL +        │
            │              │ TimescaleDB         │
            │              └──────────┬──────────┘
            │                         │
            │                  ┌──────┴───────┐
            │                  │  core-api    │  FastAPI: RBAC, JWT, CRUD,
            │                  │              │  camera→worker scheduling,
            │                  │              │  zone push, audit log
            │                  └──────┬───────┘
            │                         │ REST + WebSocket
            ▼                         ▼
   ┌──────────────────┐      ┌─────────────────┐
   │  media-gateway   │─────▶│ command-center  │  Next.js dashboard
   │  WebRTC / HLS    │      │                 │
   └──────────────────┘      └─────────────────┘
                                      ▲
                                   NGINX (TLS termination, rate limit)
```

## Why these boundaries

Each service is a distinct **failure domain**, chosen so that the failure of one
degrades the platform rather than stopping it.

| Service | Owns | Fails how |
|---|---|---|
| `vision-worker` | Cameras, decode, inference, tracking, zone/line evaluation, aggregation | One worker dies → its cameras go offline and alert; other workers unaffected. Never blocks on the DB. |
| `core-api` | Identity, authorization, configuration, audit. Never sees a video frame. | API down → dashboard read-only; detection and alerting continue. |
| `analytics-consumer` | Time-series aggregation, occupancy reconciliation, dwell time, heatmaps | Down → history has a gap that replay backfills. Live view unaffected. |
| `alert-engine` | Rule evaluation, cooldowns, escalation, operator assignment | Down → alerts delayed, then replayed from the stream. Nothing is lost. |
| `media-gateway` | Live video transport to operators | Down → no live video; all analytics, counts, and alerts still work. |
| `command-center` | Presentation | — |

The prototype's single most valuable property — *a detector crash must not take
the server down* — is preserved and generalized: **no downstream failure can
stall detection**, because detection's only obligation to anyone else is an
`XADD` onto a Redis stream.

## Video transport: not MJPEG

The prototype streams annotated MJPEG. It is ~15 lines and it was the right call
for one camera and one viewer. It re-encodes every frame, per viewer, on the
server, and its bandwidth is roughly `frame_size × fps × viewers`. Six operators
watching a 4×4 grid is 96 concurrent MJPEG streams and it collapses.

`media-gateway` serves **WebRTC** for the low-latency operator view (sub-second,
which matters when you are watching a crowd surge) and **HLS** for playback and
for the many-viewer wall display. Annotation overlays are drawn **client-side**
from the `camera.tick` / detection metadata, not burned into the video — which
means one encoded stream serves every viewer, and the operator can toggle boxes
off without a server round-trip.

## Reading order

1. [ADR 0002](../adr/0002-apache-licensed-detection-stack.md) — why not YOLO11. Read this first; it constrains everything.
2. [ADR 0004](../adr/0004-no-biometric-inference.md) — the privacy guarantee and how it is enforced.
3. [ADR 0003](../adr/0003-static-infrastructure-is-configuration-not-detection.md) — why gates and exits are polygons, not classes.
4. [ADR 0007](../adr/0007-event-spine-and-aggregation-at-the-edge.md) — the event contract.
5. [ADR 0006](../adr/0006-dwell-time-without-tracking-people.md) — occupancy and dwell time without tracking anyone.
6. [ADR 0005](../adr/0005-onnx-runtime-with-pluggable-execution-provider.md) — inference portability and capacity.
