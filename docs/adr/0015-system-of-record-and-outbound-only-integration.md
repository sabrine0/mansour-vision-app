# ADR 0015 — MANSOUR Vision is the system of record for zones and cameras; integration is outbound-only

**Status:** Accepted
**Date:** 2026-07-09
**Supersedes in practice:** Moussem migration `0016_vision_cameras.sql` and the
`vision-ingest` Edge Function, which were built for the `mar-vision/` prototype.
**Reserved:** ADRs 0008–0014 are allocated to decisions already queued from the
two SRS volumes. This is numbered 0015 rather than jumping the queue.

## Context

MANSOUR Vision does not deploy alone. Two sibling systems, both by Tomorrow
Systems, address the same event:

**Moussem Smart Guide 2026** — Supabase (PostgreSQL 15, Auth, Realtime, Edge
Functions), a Next.js organizer dashboard and an Expo visitor app, FR/AR with
RTL. It already contains vision scaffolding: `cameras`, `camera_readings`,
`camera_readings_log`, a `zone_live` view, and a `vision-ingest` Edge Function.
The migration comments name *"MAR-Vision (YOLOv8 + ByteTrack)"* — the 24-hour
prototype this platform replaces. **No dashboard or mobile code reads any of it.**

**Naviq** (formerly Wsir / SWARM AI) — Node + Express + Socket.IO + Prisma on
PostgreSQL, Railway-hosted; a driver PWA, a **police console**, and an admin
dashboard. It has an `Incident` model with an `active → verified → resolved`
lifecycle, an `official` flag, and realtime `report:*` events. It has **no
camera, video, or device model of any kind** — `IncidentType.camera` is a
speed-camera map pin.

### The problem is not the cameras. It is the geometry.

The venue's zone polygons exist in **four** places:

| Copy | Form | Consumer |
|---|---|---|
| `traffic.tomorrow.ma` "Moussem Command Center" | original export | — |
| `Naviq/backend/data/festival_moussem.json` | flat file on disk, served by `GET /festival` | Naviq police + users maps |
| Moussem `map_features` (`kind='zone'`) | `jsonb` `[lat,lng]` rings | Moussem Leaflet editor, `zone_live` |
| Moussem `crowd_zones` | circle **or** polygon, own `zone_category` enum | Moussem affluence dashboard |

Nothing reconciles them. Editing a boundary in Moussem's Leaflet editor leaves
Naviq drawing last month's polygon, because Naviq reads a file. The mahrek —
the polygon on which `HRS-006` and `HRS-007` depend, and on which a person's
life depends — is a fourth-hand copy of a decoration.

### Three artefacts of the prototype that must not survive

1. `cameras.zone_id` is a **single foreign key** to one zone, with a `coverage`
   column (0.05–1.0) scaling the count by "how much of the zone this lens sees."
   That fudge factor is standing in for the many-to-many `camera_zones` of
   `docs/architecture/data-model.md`. Two cameras on one zone double-count; one
   camera seeing three zones cannot be expressed at all.
2. `zone_live` divides a **frame count**, scaled by `coverage`, by the zone's
   ground area from an in-SQL shoelace. The result carries the *units* of
   persons/m² and none of the meaning. It is precisely the "number that looks
   authoritative and means nothing" prohibited by Detection SRS §4.1, and it is
   granted to `anon`.
3. `vision-ingest` authenticates **every camera with one shared secret**
   (`VISION_INGEST_KEY`, `verify_jwt=false`). One compromised worker forges every
   camera's readings, with no per-camera revocation.

One thing the prototype got right, and which this ADR preserves: `zone_live`
returns **null, not zero, when no camera is online**, and migration `0017` is
named `zone_live_unknown`. That is the same instinct as `HRS-007`, and it is
correct.

## Decision

### 1. MANSOUR Vision is the system of record

MANSOUR Vision owns, exclusively: `zones`, `camera_zones`, `counting_lines`,
`cameras`, calibration (homography, validity, invalidation), capacity, LOS
thresholds, and risk level.

Not because it is our project. Because it is the only one of the three where
**wrong geometry kills someone.** Moussem uses a zone to colour a bar. Naviq
uses one to draw an overlay. MANSOUR uses one to decide whether a person is
standing on a track down which fifteen horses are about to charge at 15 m/s.
Safety-critical geometry cannot be a downstream copy of a decorative one.

Corollary: capacity, risk level, calibration and `camera_zones` have nowhere to
live in either sibling schema, and adding them there would mean adding
safety-critical columns to a public-facing consumer app.

### 2. Integration is outbound-only

**MANSOUR publishes. MANSOUR reads nothing back.** There is no inbound path by
which Moussem or Naviq can mutate a zone, a camera, a threshold, or an incident.
A bug in a visitor app cannot move the mahrek boundary.

Three published feeds, all **derived, sanitized projections** — never raw events
from the spine (ADR 0007):

| Feed | To | Contents |
|---|---|---|
| **Zone registry** | Naviq, Moussem | zone id, `external_ref`, name FR/AR, kind, polygon, layer. Replaces `festival_moussem.json` and populates `map_features`. |
| **Zone occupancy** | Moussem (public affluence) | zone `external_ref`, occupancy, LOS band, confidence, `observed_at`. Subject to §4. |
| **Published incidents** | Naviq police console | summary + coordinate + severity + deep link. Subject to §5. |

### 3. Identity across the three systems

`map_features.ext_id` — the integer from the original Naviq export — is the
existing correlation key and is adopted as-is. MANSOUR `zones` gains an
`external_ref` column carrying it. The four copies collapse into one
authoritative table plus two mirrors.

Consequently, in Moussem:

* `cameras`, `camera_readings`, `camera_readings_log`, `zone_live` and the
  `vision-ingest` function are **retired**, and replaced by a single
  `zone_occupancy` mirror table written by MANSOUR's publisher.
* `crowd_zones` is retired, or reduced to a view over the mirror. Two zone
  concepts in one schema is a defect, not a feature.
* `map_features` (`kind='zone'`) becomes a **read-only mirror** of MANSOUR's
  zone registry. The Leaflet polygon editor moves to MANSOUR (`CMG-007`), where
  it must exist anyway, because only MANSOUR can show the operator where a
  drawn polygon actually lands on the ground via the camera's homography.

In Naviq, `GET /festival` serves a **cached copy** of the published zone
registry rather than a file committed to the repository. The cache is
offline-tolerant and renders **stale**, never fresh, when it is stale.

### 4. Crush risk is never public

Naviq's `Incident` feed renders on the phones of tens of thousands of drivers.
Moussem's `zone_live` is granted to `anon`. Therefore, publishable content is
restricted by a **whitelist enforced in code, not in configuration**:

**Publishable:** zone occupancy; LOS bands up to and including `Elevated`; queue
waiting time; parking availability. These are the affluence and mobility
features, and they are genuinely useful to a visitor.

**Never publishable, at any severity, by any operator action:** crush risk
(`SID-006`, `ALR-06`), density bands `High` and `Critical`, track incursion
(`ALR-01`, `ALR-03`), riderless horse (`ALR-02`), every `SID` signal, emergency
exit or route blockage, and all camera and system health.

**Broadcasting a crush warning to the crowd standing in the crush can cause the
crush.** A whitelist is the only defensible control here: an operator deciding,
under load, in the worst ninety seconds of the event, whether to press
*publish* is a control that fails exactly when it is needed. Nothing above
`warning` severity leaves the operator surfaces.

### 5. MANSOUR owns incidents; Naviq receives a summary

The incident record of Operational SRS §7 — lifecycle, timeline, ownership,
evidence with chain of custody, legal hold, append-only audit — lives in
MANSOUR. Naviq's `Incident` has none of these, has no PostGIS, no audit table,
and is a public-facing consumer app; retrofitting them onto it would put the
evidentiary record of a fatality inside a driver-navigation product.

A **confirmed, whitelisted** MANSOUR incident publishes a summary pin into
Naviq's feed as `official`, with a deep link back to the MANSOUR command center.
Status projects **one way**: MANSOUR `resolved` → Naviq `resolved`. A Naviq
officer resolving the pin does not resolve the incident, and the console says so.

### 6. Authentication

The single shared `VISION_INGEST_KEY` is retired with the function that used it.
Outbound publication uses per-consumer credentials, signed webhooks with replay
protection (`NTF-008`), and mTLS between services where the transport allows it.
`cameras.source_url` never leaves MANSOUR and never holds a plaintext credential
(`CFG-006`).

### 7. The privacy claim is scoped to MANSOUR Vision, in writing

ADR 0004's guarantee — no face recognition, no identification, no biometric
categorisation, no re-identification, no plate reading — is a property of **this
platform**. Naviq processes continuous, identified GPS from consenting drivers
(`ProbePoint`, `User.lastLat/lastLng`). That is legitimate for a navigation
product and entirely orthogonal to our claim.

But a Data Protection Impact Assessment will assess the three systems **as
deployed together**. If they are presented as one platform, "we never track
individuals" becomes false at the platform level, and the strongest thing we own
is destroyed by a marketing sentence. The scoping must be explicit in every
document that leaves the building. This is not an engineering constraint; it is
the one that costs the most to fix late.

## Consequences

**Positive.**

- One authoritative geometry. Editing the mahrek boundary changes it everywhere,
  including in the two systems that draw it for the public.
- The zone editor and calibration UI (`CMG-007`, `CAL-001`) were already required
  by Milestone 3; they now also serve the siblings, at no additional cost.
- Outbound-only means no sibling can corrupt safety-critical state, and MANSOUR
  can be tested, migrated and restarted without touching either.
- Naviq gains camera-derived incidents; Moussem gains real occupancy; neither
  gains an obligation to understand homography.

**Negative, and accepted.**

- MANSOUR must build and operate two publishers, and keep two mirrors fresh. A
  mirror is a cache, and caches go stale.
- **When MANSOUR is down, both mirrors go stale.** They must render *stale* —
  with the age of the last observation — and never render a stale figure as
  live. This is Volume II §2.7 applied across a system boundary, and it is the
  main new failure mode this ADR introduces.
- Moussem loses `crowd_zones` and its manually-set occupancy percentages. Its
  affluence screen becomes dependent on MANSOUR's availability, and must degrade
  to "unknown" rather than to zero.
- Naviq's `GET /festival` changes from a file read to a cached fetch, and needs
  an offline path — the venue is a field.
- Retiring `0016` and `0017` requires a Moussem migration that drops tables.
  Nothing reads them today, which is why this is cheap **now** and expensive
  after the visitor app ships an affluence screen against `zone_live`.
