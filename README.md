# MANSOUR Vision

**AI-Powered Event Command & Control Platform** — Tomorrow Systems.

Anonymous, real-time operational monitoring of crowds, traffic, horses, and venue
infrastructure across many cameras, in one command center.

---

## Privacy posture

The platform performs **anonymous operational monitoring only**. It does not
implement, and is architecturally incapable of, the following:

- ❌ Face recognition
- ❌ Person identification
- ❌ Biometric recognition or categorisation (including age or gender inference)
- ❌ Identity tracking or cross-camera re-identification
- ❌ License plate recognition
- ❌ Personal profiling

These are enforced by the system's structure, not by a policy document: no
component receives or transmits person crops or appearance embeddings, and track
identifiers are ephemeral, per-process, and never persisted or published.
See [ADR 0004](docs/adr/0004-no-biometric-inference.md).

Metrics that ordinarily require following individuals — average stay, waiting
time — are instead derived from aggregate flow using Little's Law.
See [ADR 0006](docs/adr/0006-dwell-time-without-tracking-people.md).

---

## Licensing posture

No component of the production image is licensed under **AGPL, GPL, or SSPL**.
Notably, `ultralytics` (YOLOv8 / YOLO11) is **excluded** — it is AGPL-3.0, and its
network clause is incompatible with proprietary deployment. Detection uses
RT-DETRv2 (Apache-2.0); tracking uses ByteTrack via `supervision` (MIT).
CI enforces this with a license gate and emits a CycloneDX SBOM per build.
See [ADR 0002](docs/adr/0002-apache-licensed-detection-stack.md).

---

## Repository layout

```
mansour-vision/
├── docs/
│   ├── adr/                    architecture decision records — start here
│   └── architecture/           system overview, data model, event contract
├── services/
│   ├── vision-worker/          decode → detect → track → zone/line → aggregate
│   ├── core-api/               FastAPI: RBAC, JWT, CRUD, scheduling, audit
│   ├── analytics-consumer/     aggregation, occupancy reconciliation, dwell time
│   ├── alert-engine/           rules, cooldowns, escalation, assignment
│   └── media-gateway/          WebRTC / HLS video transport
├── apps/
│   └── command-center/         Next.js operator dashboard
├── packages/
│   ├── contracts/              event + API schemas — the source of truth
│   └── py-common/              config, logging, tracing, db base
├── infra/
│   ├── docker/  nginx/  compose/
└── ops/
    └── benchmarks/             per-host camera capacity harness
```

`contracts/` is generated from, and validated against, both the Python services
and the TypeScript frontend. A schema change that breaks either side fails CI.

---

## Relationship to `mar-vision/`

`../mar-vision/` is the 24-hour single-camera prototype. It is **preserved as a
reference and is not extended.** Its detection geometry (line-crossing side tests,
track lifecycle), its frame-staleness-based camera-offline rule, and its
per-scope alert cooldowns were correct and are carried forward into
`services/vision-worker` and `services/alert-engine`. Its process model — one
thread, one camera, one global settings object, SQLite in the hot path, MJPEG
transport — is not.

---

## Status

**Milestone 2 complete** — the monorepo, the shared packages, the event contract,
four runnable Python service shells, the command-center dashboard, and the full
local stack.

The services start, report their health truthfully, and shut down gracefully.
**They do not yet open a camera, run a model, or write a row** — and they do not
pretend to. Camera management, the database schema, and live telemetry are
Milestone 3.

```bash
make install && make secrets   # first run
make check                     # everything CI runs
make up                        # the whole stack
```

See [`docs/development.md`](docs/development.md) to get started, and
[`docs/architecture/system-overview.md`](docs/architecture/system-overview.md)
for why the services are divided as they are.

See [`docs/deployment.md`](docs/deployment.md) for secret validation, stack
hardening, and the remaining production requirements.
