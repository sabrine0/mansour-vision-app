# Integration — Moussem and Naviq

How MANSOUR Vision connects to its two sibling systems. Governed by
[ADR 0015](../adr/0015-system-of-record-and-outbound-only-integration.md); read
that first for *why*.

```
                    ┌──────────────────────────────────────┐
                    │        MANSOUR VISION                │
                    │  system of record:                   │
                    │   zones · camera_zones · cameras     │
                    │   calibration · capacity · risk      │
                    │   alerts · incidents · evidence      │
                    └───────────────┬──────────────────────┘
                                    │ outbound only
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
     ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
     │ zone registry  │   │ zone occupancy   │   │ published        │
     │ (geometry)     │   │ (sanitized)      │   │ incidents        │
     └───────┬────────┘   └────────┬─────────┘   └────────┬─────────┘
             │                     │                      │
      ┌──────┴───────┐             ▼                      ▼
      ▼              ▼      ┌─────────────┐      ┌──────────────────┐
 ┌─────────┐   ┌─────────┐  │  MOUSSEM    │      │ NAVIQ police     │
 │ NAVIQ   │   │ MOUSSEM │  │  affluence  │      │ console          │
 │ /festival│  │map_features│ (public)   │      │ (official pins)  │
 └─────────┘   └─────────┘  └─────────────┘      └──────────────────┘
```

**No arrow points back.** Neither sibling can mutate a zone, a camera, a
threshold, or an incident.

---

## 1. Zone registry (geometry)

MANSOUR is authoritative. Published on change, and on a slow heartbeat so a
missed change eventually reconciles.

Each zone carries: `id` (MANSOUR uuid), `external_ref` (the integer `ext_id`
from the original Naviq export — the correlation key across all three systems),
`name_fr` / `name_ar`, `kind`, `layer_key`, and the polygon ring as `[lat, lng]`
pairs (the convention both siblings already use; GeoJSON `[lng, lat]` is flipped
at the boundary, once, here).

**Deliberately not published:** capacity, LOS thresholds, risk level,
`camera_zones`, calibration, camera positions, or any camera identifier. A
visitor app has no use for the mahrek's capacity, and a leaked camera inventory
is a reconnaissance gift.

Consumers:

- **Naviq** — `GET /festival` becomes a cached fetch of this registry instead of
  reading `backend/data/festival_moussem.json`. The cache is written to disk and
  is offline-tolerant: the venue is a field, and the police console must draw the
  map when nothing is reachable. A stale cache renders *with its age*.
- **Moussem** — `map_features` (`kind='zone'`) becomes a read-only mirror. The
  Leaflet polygon editor in `apps/dashboard/src/components/map/SiteMap.tsx` is
  retired in favour of `CMG-007`, which shows the operator the polygon projected
  onto the ground plane through the camera's homography. Drawing a boundary you
  cannot see the ground-truth of is how a zone ends up ten metres off.

---

## 2. Zone occupancy (sanitized, public)

Replaces Moussem's `cameras`, `camera_readings`, `camera_readings_log`,
`zone_live` and the `vision-ingest` Edge Function, all of which are dropped.

Published at low frequency (~10 s, not 1 Hz — a bar chart does not need a
hertz) into a single Moussem mirror table, keyed by `external_ref`.

Each record carries `occupancy`, `los_band`, `confidence`, `observed_at`, and
`anchor_age_seconds`.

### The whitelist, enforced in code

`los_band` is published only when it is `uncalibrated`, `normal`, or `elevated`.

When the true band is `high` or `critical`, the published band is **`elevated`**
and a flag `capped: true` is set. The public surface says "busy." It never says
"dangerous," because **broadcasting a crush warning to the crowd standing in the
crush can cause the crush** (ADR 0015 §4).

Never published on any public surface, at any severity, by any operator action:

| | |
|---|---|
| `ALR-06` crush risk | `ALR-01` / `ALR-03` track incursion |
| `ALR-02` riderless horse | every `SID` signal |
| density bands `High`, `Critical` | emergency exit / route blockage |
| camera health, system health | camera identifiers, snapshots, stream URLs |

This is a whitelist, not a blacklist, and it lives in the publisher's code with
a test that fails if a new alert category defaults to publishable.

### Staleness

`zone_live`'s one correct instinct is preserved and generalized: **when MANSOUR
has no fresh observation for a zone, the mirror carries no value — not zero.**
Moussem's affluence screen renders "—" and the age of the last observation.

When MANSOUR is unreachable entirely, the mirror is stale by definition. Moussem
must render every value as stale with its age, and must not present a
five-hour-old occupancy as current. This is Volume II §2.7 across a system
boundary, and it is the principal new failure mode ADR 0015 introduces.

---

## 3. Published incidents (police)

MANSOUR owns the incident record: lifecycle, timeline, ownership, evidence with
chain of custody, legal hold, append-only audit (Operational SRS §7, §13, §18).
Naviq's `Incident` model has none of these and is a public-facing consumer app.

A MANSOUR incident is published to Naviq only when **all** hold:

1. It has been **confirmed by an operator** — never on alert-raise, never
   automatically.
2. Its category is on the publishable whitelist.
3. Its severity is at most `warning`.

The published pin carries a title, a category, a ground coordinate, a timestamp,
and a **deep link back into the MANSOUR command center**. It carries no snapshot,
no camera id, no evidence reference, and no personal data of any kind.

**Status projects one way.** MANSOUR `resolved` → Naviq `resolved`. An officer
resolving the pin in Naviq does *not* resolve the MANSOUR incident, and the
Naviq console states this on the pin. A one-way projection that pretends to be
bidirectional is worse than no integration: it produces an incident that looks
closed to everyone and is owned by no one.

Transport: signed webhook (`NTF-008`) into a new Naviq endpoint accepting only
`official` incidents from an authenticated MANSOUR credential, plus the existing
Socket.IO `report:new|update|remove` fan-out to the police console, which needs
no change.

---

## 4. Authentication

The shared `VISION_INGEST_KEY` is retired along with `vision-ingest`.

- Per-consumer credentials, one per sibling, independently revocable.
- Signed webhooks with a timestamp and nonce; replay outside the window is
  rejected.
- mTLS between services where the transport allows it.
- `cameras.source_url` never leaves MANSOUR and holds a secret reference, never
  a plaintext RTSP credential (`CFG-006`).

Every publication is an audited event (`AUD-002`): what was published, to whom,
under whose authority, and — for incidents — which operator confirmed it.

---

## 5. Privacy scoping

ADR 0004's guarantee is a property of **MANSOUR Vision**, not of the three
systems collectively. Naviq processes continuous identified GPS from consenting
drivers; that is legitimate for a navigation product and orthogonal to our claim.

A Data Protection Impact Assessment will assess the systems **as deployed
together**. Every document, deck, and datasheet that leaves the building must
scope the claim explicitly. Nothing in the integration moves personal data
between the systems, and nothing published by MANSOUR identifies, tracks, or
characterises a person — but the *claim* must be stated at the right scope, or
the strongest thing this platform owns is destroyed by a sentence in a slide.

---

## 6. Migration plan

Ordered so that nothing breaks at any step. Nothing in Moussem reads the vision
tables today, which is why steps 2–3 are cheap **now** and expensive once the
visitor app ships an affluence screen against `zone_live`.

### The seed data is geometry, not a zone registry

`Naviq/backend/data/festival_moussem.json` is a `moussem-backup` export
(v1.0, SRID 4326, GeoJSON `[lng, lat]`, exported 2026-07-06) containing 93
features: 53 points, 7 lines, **33 polygons** across 8 layers.

Inspected directly, the polygons are:

* **All labelled `"Zone"`** (or `"Zone Parking"`). They are distinguished from
  one another **only by hex colour**. None carries a name, a `kind`, a capacity,
  or a risk level.
* **All carrying `densite_base: 3.5`** — an identical hard-coded constant, not a
  measurement. 3.5 persons/m² falls inside the Fruin **`High`** band, where
  involuntary contact begins. Moussem's `map_features.props.densiteBase` inherits
  it. Nothing currently reads it, and nothing ever should: rendering it as an
  estimate would be inventing a crowd-safety figure from a drawing tool's default.

**Nothing in the export identifies the mahrek.** `HRS-006` — the highest-severity
requirement in the specification — cannot be built against a polygon named
`Zone` whose only distinguishing property is that it is pink.

The geometry is genuinely valuable: it is a real survey of real boundaries and it
saves the survey. It is **not** a zone registry. Step 1 below is therefore a
working session with the event safety officer, not an import script.

| # | Where | Change | Reversible |
|---|---|---|---|
| 1a | MANSOUR | `zones.external_ref`; ingest the 33 polygons as **unnamed, untyped geometry**, explicitly marked *unclassified* and barred from every alert rule | yes |
| 1b | — | **Classification session with the safety officer**: name and type all 33 (which is the mahrek, the horse waiting area, the emergency routes), set capacity and risk level, sign off LOS thresholds (`ZON-002`, `EVT-006`). Discard `densite_base`. | — |
| 2 | MANSOUR | Zone registry publisher + zone editor (`CMG-007`) | yes |
| 3 | Moussem | `map_features` becomes a read-only mirror; retire the Leaflet editor | yes |
| 4 | Moussem | Drop `cameras`, `camera_readings`, `camera_readings_log`, `zone_live`; drop the `vision-ingest` function; add the `zone_occupancy` mirror | **one-way** |
| 5 | Moussem | Retire `crowd_zones`, or reduce it to a view over the mirror | one-way |
| 6 | Naviq | `GET /festival` → cached fetch of the zone registry, offline-tolerant | yes |
| 7 | Naviq | Inbound published-incident endpoint | yes |
| 8 | MANSOUR | Occupancy publisher and incident publisher, with the whitelist test | yes |

Steps 1–3 are Milestone 3 work and overlap the zone editor that milestone must
build regardless. Steps 4–8 follow Milestone 4, once there is real detection to
publish. **No sibling change ships before MANSOUR can actually produce the data
it is about to become dependent on.**

---

## 7. Open questions

1. Is `traffic.tomorrow.ma` — the Command Center that produced
   `festival_moussem.json` — still maintained, and does anything still consume
   it? If so it needs to become a consumer of the registry too, or be retired.
2. Who operates Naviq's police console during the moussem: the same officers who
   sit at the MANSOUR command center, or a different team? This decides whether
   the deep link is useful or decorative.
3. Moussem's `crowd_zones.zone_category` (`tente | parking | mahrek | esplanade |
   restauration | secours | souk | autre`) is a real, event-specific vocabulary.
   Should MANSOUR's `zones.kind` adopt these names rather than the generic set in
   `data-model.md`? The operators already use them.
4. Does the visitor app's affluence screen ship before the event? It is the only
   consumer that makes the occupancy publisher urgent.
5. **Who can identify the 33 polygons?** Which is the mahrek, which are the
   emergency routes, which is the horse waiting area? Until someone who knows the
   venue answers this, no P0 horse alert and no crush-risk alert can be
   configured, and the geometry is only a picture. This blocks Milestone 3.
6. `densite_base: 3.5` is a uniform constant across all 33 polygons. Confirm it
   was a drawing-tool default and was never intended as a density estimate. If
   anything downstream reads it today, that must stop.
