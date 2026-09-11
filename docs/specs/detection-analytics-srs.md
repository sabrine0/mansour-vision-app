# MANSOUR Vision — Detection & Analytics Specification

**Software Requirements Specification (SRS) · Part 1 of 1**

| | |
|---|---|
| **Document** | Detection & Analytics Specification |
| **Version** | 1.0 |
| **Status** | For review — senior engineering, government stakeholders, project management |
| **Date** | 2026-07-09 |
| **Owner** | Technical Director, Tomorrow Systems |
| **Baseline** | ADR 0001–0007 (`docs/adr/`). This document does not revisit them. |
| **Primary deployment** | Moussem Moulay Abdellah |

---

## 1. Purpose and scope

This document specifies **what MANSOUR Vision must observe, measure, infer, and
alert on**. It is a requirements document, not a design document. It contains no
implementation code, no API definitions, and no database schema — those live in
`docs/architecture/`.

It is written to be read by three audiences with different questions:

- **Senior engineers** ask *"is this buildable, and what is it going to cost?"*
  Every feature carries a complexity estimate and an honest statement of what the
  AI can and cannot do.
- **Government stakeholders** ask *"what does this system know about people, and
  what will it do at 3pm on the busiest day?"* Every feature states its business
  value and its privacy posture.
- **Project managers** ask *"what ships when?"* Every feature is assigned to one
  of four roadmap phases (§16).

### 1.1 What is out of scope, permanently

Per [ADR 0004](../adr/0004-no-biometric-inference.md), and repeated here because
this document will be read by people who have not read the ADRs:

The platform performs **anonymous operational monitoring only**. It does not
perform face recognition, person identification, biometric recognition or
categorisation (including age, sex, or gender inference), identity tracking,
cross-camera re-identification, license plate recognition, or personal profiling.

**No feature in this specification classifies the conduct, intent, or attributes
of an individual person.** Where the operational need appears to require it —
lost children, altercations — the requirement is restated as an anonymous,
aggregate, geometric signal that directs an operator's attention to a location.
The system says *"look here."* It never says *"this person is X."*

---

## 2. Operating context: the Moussem Moulay Abdellah

The deployment target is not a generic large event, and specifying it as one
would produce a system that fails on its first day. Four properties of this
venue dominate the requirements.

### 2.1 Tbourida is the centre of the event, and it is a horse-and-firearm performance

Tbourida (*fantasia*) is performed by a **sorba** — a troop of horsemen who
charge in line abreast down a prepared track and discharge black-powder muskets
in unison at the end of the run. Consequences for this system:

- **Gunpowder smoke is expected, scheduled, and voluminous.** A conventional
  smoke detector would raise a critical alarm on every single run, several times
  an hour, for the entire event. Within one day, operators would ignore the
  alert channel entirely — which is worse than having no smoke detection at all.
  This is addressed by **contextual arming** (§4.3).
- **The charge track is a lethal zone during a run.** A spectator, child, dog, or
  vehicle on the track while a sorba is charging is the highest-severity event
  this platform can detect. **Track incursion detection is the single most
  important requirement in this document** (`HRS-006`).
- **A riderless horse mid-charge means a rider has fallen at speed.** This is a
  directly detectable, unambiguous, high-value safety signal that requires no new
  model (`HRS-004`).
- **Dust and motion blur** from a charging line degrade detection recall exactly
  when the system is most needed. This is an accuracy risk, not a design flaw,
  and it is stated in the risk register (§17).

### 2.2 The crowd is schedule-driven, not stochastic

Attendance rises and falls around the tbourida programme and around the five
daily prayers. A static occupancy threshold will alarm every day at prayer time
when the prayer area fills, and again when it empties — behaviour that is
entirely normal. **Alert thresholds must be time-aware and programme-aware**
(§4.3). The event schedule is therefore a **first-class system input** (§11),
not a documentation artifact.

### 2.3 The event runs into the night

Low-light and IR imagery degrade a detector trained on daytime RGB. Detection
confidence, and therefore density and counting accuracy, will fall after dusk.
The system must **measure and display this degradation** rather than silently
report a lower crowd count as though it were real (`CAM-011`, `SYS-011`).

### 2.4 Horses, vehicles, and dense pedestrian crowds share space

Most crowd-analytics products assume pedestrians only. Here, a 500 kg animal at
speed, a horse trailer reversing, and a crowd at 4 persons/m² occupy adjacent
zones. Proximity between these is itself a monitored quantity (`HRS-015`).

### 2.5 Domain assumptions requiring client confirmation

Stated explicitly so they can be corrected before development, rather than
discovered during it:

| # | Assumption | Confidence | Impact if wrong |
|---|---|---|---|
| A1 | The charge track and the sorba formation are the correct operational units to model | High | Restructures `HRS` module |
| A2 | A machine-readable (or manually enterable) event programme will be available before each day | Medium | Contextual arming (§4.3) degrades to manual operator arming |
| A3 | Cameras may be physically surveyed for ground-plane calibration before the event | **Medium — must confirm** | Density reverts to uncalibrated counts; all crush-risk alerts become undefendable |
| A4 | Expected peak attendance and per-zone capacities will be supplied by the event safety officer | Low — not yet supplied | All occupancy thresholds are placeholders |
| A5 | Venue power and network at camera positions support continuous streaming | Unknown | Changes deployment topology to edge inference |

Local terminology used in this document (*sorba*, *mahrek*, *baroud*) should be
reviewed by the client and corrected where wrong. The engineering does not depend
on the terminology; the operator UI does.

---

## 3. Reading the feature catalogue

Every feature is specified with the same seven fields.

- **Feature name** and a stable **ID** (`MOD-NNN`). IDs are permanent and are
  referenced by the alert catalogue (§9), the test plan, and the roadmap.
- **Description** — what it does, in operational terms.
- **Business value** — why an operator, a safety officer, or an organizer cares.
  If this field is weak, the feature should not be built.
- **Priority** — `P0` safety-critical, cannot ship without · `P1` core product ·
  `P2` valuable · `P3` differentiator / future.
- **Complexity** — `S` (days) · `M` (1–2 weeks) · `L` (3–6 weeks) · `XL` (a
  quarter or more, or blocked on data collection).
- **AI required** — the honest answer, from this ladder:
  - `None` — pure geometry, configuration, or telemetry. No model.
  - `Detector` — the RT-DETRv2 pass we already run. Effectively free.
  - `Detector + Tracker` — adds ByteTrack state.
  - `Flow` — dense optical flow over the frame. Anonymous by construction; sees
    motion fields, not people.
  - `Custom model` — requires a labelled dataset from this venue. **This is the
    expensive answer**, and it is why so few features carry it.
  - `Non-vision` — comes from an integration, a sensor, or an operator.
- **Future improvements** — the next increment, once the base version is live.

Two notes on complexity. First, a feature marked `Detector` is *nearly free*
because the inference pass is already paid for by `PPL-001`; the cost is the rule
on top. Second, `Custom model` complexity is dominated by **data collection and
annotation, not engineering** — you cannot compress it by adding developers.

---

## 4. Foundational measurement decisions

Three decisions taken before the catalogue, because most features depend on them.

### 4.1 Density is persons per square metre, not persons per frame

The prototype counts people in the frame and compares that to a threshold. This
number is **not comparable between cameras**: a wide-angle camera covering
400 m² and a zoomed camera covering 40 m² both report "15 people," and one of
those is an empty field while the other is a dangerous crush. Thresholds tuned
per camera drift the moment a camera is nudged, and no such number can be
defended to a safety officer.

Therefore: **each camera is calibrated once, by homography, against four or more
surveyed ground reference points**, mapping image pixels to venue ground
coordinates. Density is then computed as persons per square metre of ground area,
and is directly comparable across every camera and every zone.

This unlocks the **Fruin Level of Service** bands, which are the established
vocabulary of crowd safety and which a safety officer already understands. The
default bands below are **placeholders pending sign-off by the event safety
officer** (assumption A4) and are configurable per zone, because a critical
density in a prayer area is not a critical density in a market aisle:

| Band | Default | Operational meaning |
|---|---|---|
| Normal | < 2.0 p/m² | Free movement |
| Elevated | 2.0 – 3.5 p/m² | Movement constrained, monitor |
| High | 3.5 – 4.5 p/m² | Involuntary contact; intervention should begin |
| Critical | ≥ 4.5 p/m² | Crush-risk regime; immediate intervention |

**Density alone is an incomplete predictor of a crowd crush.** The crowd-safety
literature is consistent that crushes are preceded by *turbulent, oscillating
pressure* in an already-dense crowd, not by density crossing a line. A crowd can
sit at 4 p/m² safely for an hour and then kill people in ninety seconds when flow
becomes turbulent. `PPL-012` specifies turbulence as a distinct signal for
exactly this reason, and it is the most important analytics feature in this
document after track incursion.

**Calibration is therefore a prerequisite**, not an enhancement. An uncalibrated
camera must render its density as *uncalibrated* in the UI and must not raise
crush-risk alerts. Silently degrading to counts would be the most dangerous
possible failure mode: a number that looks authoritative and means nothing.

### 4.2 Detection tiers (restated from ADR 0003, not re-derived)

- **Detected** by the model: `person`, `horse`, `dog`, `car`, `truck`, `bus`,
  `motorcycle`, `bicycle`. These are pretrained COCO classes and cost nothing.
- **Configured** once by an operator: every static feature — gates, exits, the
  charge track, parking areas, restricted zones — as a polygon.
- **Derived** by rules over the two: every alert in this document.
- **Compositional**: horse-rider is `person` ∩ `horse`, not a class.

**An honest note on vehicle sub-types.** The specification requests `SUV`,
`pickup`, and `van`. COCO contains none of these — it has `car`, `truck`, and
`bus`. Distinguishing an SUV from a car by bounding-box size is unreliable
(it depends on range, which depends on calibration, and a distant SUV and a near
car are indistinguishable). Fine-grained vehicle typing is a `Custom model` item
(`VEH-002`), deferred, and the platform must not pretend otherwise in v1.

### 4.3 Alerts are contextually armed, not globally enabled

Every alert rule has an **arming context**: the set of zones it watches and the
time windows in which it is live. Contexts are driven by the event programme.

The motivating case is baroud smoke (§2.1): the smoke rule is **disarmed for the
charge track and its downwind cone for the duration of each scheduled sorba run,
and auto-rearms afterwards.** Smoke in that zone outside a run, or smoke in any
other zone at any time, alarms normally. A real fire on the track between runs is
still detected.

This generalizes. Prayer-area occupancy thresholds relax during prayer. Parking
inflow alerts arm before gates open. Track-incursion detection escalates from
`warning` to `critical` the moment a sorba is staged.

**Arming state is always visible to the operator**, and every automatic arm/disarm
is written to the audit log. An operator can manually re-arm any suppressed rule
in one click. A system that silently disables its own alarms is not a safety
system; a system that shows you which alarms are off, and why, is.

---

## 5. PEOPLE (`PPL`)

### PPL-001 — Person detection
**Description.** Per-frame detection of persons as anonymous bounding boxes, at
the configured analytic FPS. The foundation of every other feature in this
section. Produces no identity, no crop, no embedding.
**Business value.** Nothing else in the platform works without it.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** Small-object recall tuning for distant crowds; a tiled inference pass
for wide-angle cameras where distant people fall below the detector's minimum box
size.

### PPL-002 — Live people count, per zone
**Description.** Count of distinct person detections whose ground-plane footprint
falls inside a zone polygon, de-duplicated across overlapping cameras by geometry
(never by appearance). Published at 1 Hz.
**Business value.** The number an operator looks at first. Drives every zone
status indicator in the command center.
**Priority** P0 · **Complexity** M · **AI** Detector
**Future.** Confidence-weighted counting, so low-confidence detections at night
contribute fractionally rather than being thresholded in or out.

### PPL-003 — Entry counting
**Description.** Directional line-crossing counts per virtual line, per class.
Decided from the track's centroid history crossing the line segment with a
direction test — not from raw track identity, so an ID switch cannot double-count.
Multiple lines per camera.
**Business value.** Regulatory occupancy compliance; gate throughput; the input
to every flow and dwell metric.
**Priority** P0 · **Complexity** S · **AI** Detector + Tracker
**Future.** Multi-line consensus, where two lines a metre apart must both be
crossed in order, eliminating loiter-on-the-line miscounts.

### PPL-004 — Exit counting
**Description.** As `PPL-003`, opposite polarity. Direction is declared
explicitly per line (`inward_side`), never inferred from endpoint order.
**Business value.** Half of occupancy; the primary evacuation-progress metric.
**Priority** P0 · **Complexity** S · **AI** Detector + Tracker
**Future.** Emergency mode in which all lines are treated as exits and the
dashboard reports "persons remaining" rather than "persons present."

### PPL-005 — Zone occupancy (reconciled)
**Description.** Occupancy maintained by net line crossings between anchors, and
periodically **re-anchored** to the direct in-zone count (`PPL-002`), per
[ADR 0006](../adr/0006-dwell-time-without-tracking-people.md). Carries a
confidence and the age of its last anchor. Known-empty zones hard-reset to zero
and the residual is logged as the day's accumulated counting error.
**Business value.** An occupancy number that does not drift into fiction by hour
six, and that tells you how much to trust it. Most systems in this class never
find out how wrong they are.
**Priority** P0 · **Complexity** L · **AI** Detector + Tracker
**Future.** Kalman fusion of the counting estimate and the density estimate,
weighted by each one's measured variance, rather than periodic hard re-anchoring.

### PPL-006 — Venue-wide occupancy
**Description.** Sum of perimeter-gate net flow, reconciled against the sum of
zone occupancies. A divergence between the two is itself a health signal — it
means people are somewhere the zones do not cover.
**Business value.** The single number the event director and the authorities ask
for. Legal capacity compliance.
**Priority** P0 · **Complexity** M · **AI** Detector + Tracker
**Future.** Live comparison against the venue's licensed capacity with a
projected time-to-capacity, from current inflow rate.

### PPL-007 — Crowd density (persons/m²) and Fruin Level of Service
**Description.** Ground-plane density per zone via homography (§4.1), classified
into configurable LOS bands. Uncalibrated cameras report *uncalibrated* and are
excluded from crush-risk alerting.
**Business value.** The measurement on which every crowd-safety decision at this
event will be made, in the units the safety officer already thinks in.
**Priority** P0 · **Complexity** L · **AI** Detector
**Future.** Density estimation by crowd-counting regression (a density-map model)
rather than by detection, for crowds beyond ~5 p/m² where individual detection
recall collapses under occlusion. **This is a known ceiling of the detection-based
approach and the single most important accuracy investment in the roadmap.**

### PPL-008 — Crowd flow field (speed and direction)
**Description.** Dense optical flow over the frame, projected to the ground
plane, aggregated into a per-zone vector field: mean speed (m/s) and direction.
Operates on motion, not on people — it is anonymous by construction and works
where individual detection fails.
**Business value.** Sees the crowd as a fluid, which is what it is at high
density. Detects stoppage and surge before a counter can.
**Priority** P1 · **Complexity** M · **AI** Flow
**Future.** Fuse flow with detection so that flow speed is normalized by density,
yielding the fundamental crowd diagram (speed vs density) per zone.

### PPL-009 — Dominant crowd direction
**Description.** Principal direction of the flow field per zone, with a coherence
score (how aligned the crowd is). Rendered as an arrow on the map.
**Business value.** Answers "where is everyone going" during ingress, egress, and
incident response, at a glance.
**Priority** P1 · **Complexity** S · **AI** Flow
**Future.** Predicted arrival load on downstream zones, from direction plus speed
plus count.

### PPL-010 — Crowd flow rate (throughput)
**Description.** Persons per minute per metre of effective width, across a line
or gate. Normalizing by width is what makes gates comparable to each other and to
published safe-flow limits.
**Business value.** Identifies which gate is the constraint during ingress; the
core input to evacuation-time modelling.
**Priority** P1 · **Complexity** M · **AI** Detector + Tracker
**Future.** Live evacuation-time estimate per zone: `occupancy ÷ Σ egress capacity`.

### PPL-011 — Counterflow detection
**Description.** A statistically significant subpopulation of the flow field
moving against the dominant direction in a zone designed for one-way movement.
**Business value.** Counterflow in a dense unidirectional crowd is a documented
precursor to compression incidents, and it is invisible to a counter.
**Priority** P1 · **Complexity** M · **AI** Flow
**Future.** Automatic identification of the location where the counterflow
originates — usually a blocked exit or a misdirected crowd.

### PPL-012 — Crowd turbulence / pressure (crush precursor)
**Description.** Velocity-variance of the flow field within a high-density zone —
the degree to which the crowd is moving *inconsistently* rather than as a body.
Combined with density into a crush-risk indicator. High density with laminar flow
is safe; high density with turbulent flow is a developing crush.
**Business value.** **This is the feature that saves lives.** Density alone is a
lagging and incomplete indicator; turbulence at high density is the recognized
precursor to progressive crowd collapse, and it manifests as observable
oscillating motion before anyone falls.
**Priority** P0 · **Complexity** L · **AI** Flow
**Future.** Validation against recorded incident footage to calibrate thresholds;
zone-specific tuning. **This feature must not ship with unvalidated thresholds —
see §17, R-03.**

### PPL-013 — Queue detection and length
**Description.** Sustained, low-speed, high-density linear formation within a
zone of `kind=waiting` or upstream of a checkpoint. Length in metres and in
persons, from ground-plane geometry.
**Business value.** Queue length is the primary visitor-experience metric and the
leading indicator of gate under-provisioning.
**Priority** P1 · **Complexity** M · **AI** Detector + Flow
**Future.** Automatic queue-shape learning, so operators need not draw the
polygon; serpentine queue handling.

### PPL-014 — Queue waiting time
**Description.** Mean waiting time by Little's Law, `W = L / λ` — zone occupancy
divided by arrival rate. **Follows no individual.** Suppressed (rendered "—",
never `0`) when arrival rate approaches zero or when occupancy is changing faster
than the 10-minute window can absorb.
**Business value.** "The north gate is running eight minutes" is the sentence
that lets an operator open another lane. Delivered with no tracking of any person,
which is a stronger position than any competitor's per-individual dwell time.
**Priority** P1 · **Complexity** M · **AI** None (arithmetic over `PPL-005`, `PPL-003`)
**Future.** Per-lane waiting time at multi-lane checkpoints; publish estimated
wait to visitor-facing signage.

### PPL-015 — Queue collapse detection
**Description.** Rapid loss of queue structure: a sharp drop in flow coherence
with sustained or rising density. The orderly line has become a press.
**Business value.** A queue that collapses at a gate is the classic ingress
crush scenario. Detecting the transition — rather than the outcome — is the whole
point.
**Priority** P1 · **Complexity** L · **AI** Flow · Feeds `SID`
**Future.** Distinguish collapse-from-surge (pressure from behind) from
collapse-from-blockage (gate stopped), which require opposite interventions.

### PPL-016 — Bottleneck detection
**Description.** A location where upstream density and inflow are high, local
speed is low, and downstream density is low. That signature — not any one of its
parts — is a bottleneck.
**Business value.** Tells operations exactly where to add stewards or open a
barrier, rather than that "the area is crowded."
**Priority** P1 · **Complexity** L · **AI** Detector + Flow
**Future.** Bottleneck severity ranked by the queue it is generating and by
projected time to critical density upstream.

### PPL-017 — Gathering / unusual stationary crowd
**Description.** Formation of a dense, stationary cluster in a zone where the
baseline is transit, persisting beyond a threshold. Baseline is learned per zone
per time-of-day, so a stall that is always busy is never anomalous.
**Business value.** An unplanned gathering is either an incident, an obstruction,
or an attraction. All three warrant a look.
**Priority** P2 · **Complexity** M · **AI** Detector + Flow · Feeds `SID`
**Future.** Growth-rate estimation, so a gathering that is doubling every minute
ranks above one that is static.

### PPL-018 — Crowd dispersion and convergence
**Description.** Divergence of the ground-plane flow field. Strongly positive
divergence means people are moving *away* from a point — the signature of a crowd
fleeing something. Strongly negative means convergence on a point.
**Business value.** Sudden dispersion is the most reliable anonymous indicator
that *something happened* — a fall, a fight, a fire, a collapsed structure — with
no need to classify what. Convergence indicates an unplanned attraction or an
obstruction forming.
**Priority** P1 · **Complexity** M · **AI** Flow · Feeds `SID`
**Future.** Localize the divergence source to a coordinate and slew a PTZ camera
to it automatically.

### PPL-019 — Heatmaps
**Description.** Ground-plane accumulation of person presence over a selectable
window, rendered on the venue map. Spatial (where) and temporal (when) variants.
Aggregate only; no path of any individual is stored or renderable.
**Business value.** Post-event: vendor placement, gate sizing, layout planning.
Live: instant visual identification of the hottest area.
**Priority** P2 · **Complexity** M · **AI** Detector
**Future.** Comparative heatmaps across days and across years; overlay of
heatmap against incident locations.

### PPL-020 — Peak occupancy and visitor statistics
**Description.** Peak concurrent occupancy per zone and venue-wide, with
timestamp; total unique-entry count (a count of entries, not of persons — the
system cannot know if someone re-entered, and does not try); hourly and daily
profiles.
**Business value.** The core of the post-event report to the organizer and the
authorities. Evidence of capacity compliance.
**Priority** P1 · **Complexity** S · **AI** None (aggregation)
**Future.** Year-over-year comparison; correlation against weather and programme.

### PPL-021 — Lost-person advisory
**Description.** Per [ADR 0004](../adr/0004-no-biometric-inference.md): a
small-stature detection — measured as a *bounding-box height percentile relative
to other persons in the same zone*, never as an absolute age claim — that is
stationary and spatially isolated from crowd flow for longer than N minutes,
raises an advisory for an operator to look at with their own eyes.
**Business value.** Meets the real operational need behind the rejected "child
detection" feature. The system asserts *"something at these coordinates warrants
a human look."* It never asserts *"this is a child."*
**Priority** P2 · **Complexity** M · **AI** Detector + Tracker
**Future.** Reunification workflow support (operator marks resolved; the advisory
and its snapshot are purged immediately rather than at the 30-day retention
boundary).

### PPL-022 — Falling person detection
**Description.** Detection of a person transitioning to a prone posture, from
bounding-box aspect ratio inversion plus a sudden vertical centroid drop,
sustained. **Explicitly not pose estimation of an identified individual.**
**Business value.** A fall in a dense crowd is the initiating event of a
progressive crowd collapse. Seconds matter.
**Priority** P2 · **Complexity** L · **AI** Detector + Tracker · Feeds `SID`
**Future.** This is honestly hard. In the dense crowds where a fall matters most,
occlusion means the fallen person is invisible within a second. **`PPL-018`
(dispersion) and `PPL-012` (turbulence) will in practice detect a fall in a dense
crowd more reliably than `PPL-022` will**, by observing the crowd's reaction
rather than the person. `PPL-022` is specified for sparse and moderate zones,
where it works, and its limits are documented rather than hidden. Phase 3.

---

## 6. VEHICLES (`VEH`)

### VEH-001 — Vehicle detection (coarse classes)
**Description.** Detection of `car`, `truck`, `bus`, `motorcycle`, `bicycle` as
anonymous boxes. **No license plate is read, ever** (ADR 0004).
**Business value.** Foundation of all traffic, parking, and access-control
analytics.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** Tiled inference for distant approach roads.

### VEH-002 — Fine-grained vehicle typing (SUV / pickup / van)
**Description.** Distinguishing SUV, pickup, and van from `car` and `truck`.
**Business value.** Marginal. Parking-space sizing and access-permit matching.
**Priority** P3 · **Complexity** XL · **AI** Custom model
**Future.** These classes do not exist in COCO. Size-based heuristics are
unreliable, because apparent size depends on range and a distant SUV is
indistinguishable from a near car. Requires a labelled dataset from this venue.
**Deferred; the v1 UI must present coarse classes honestly rather than guess.**

### VEH-003 — Vehicle counting and direction
**Description.** Directional line-crossing counts per class, sharing the
implementation of `PPL-003`.
**Business value.** Gate and access-road load; input to parking occupancy.
**Priority** P1 · **Complexity** S · **AI** Detector + Tracker
**Future.** Per-approach origin-destination matrices across the venue's gates,
from line-crossing sequence — an aggregate flow statistic, computed without
following any individual vehicle across cameras.

### VEH-004 — Vehicle speed estimation
**Description.** Ground-plane displacement over time, using the same homography
as density (§4.1). Accuracy depends entirely on calibration quality.
**Business value.** Speeding vehicles near pedestrian zones and horse areas are a
direct safety hazard.
**Priority** P2 · **Complexity** M · **AI** Detector + Tracker
**Future.** This is **not enforcement-grade and must never be presented as such**
— it is an operational advisory. Enforcement requires certified equipment and the
identification of vehicles, which this platform will not do.

### VEH-005 — Traffic density and vehicle flow
**Description.** Vehicles per unit length of roadway, and vehicles per minute
across a line, per approach.
**Business value.** Predicts congestion on access roads before it reaches the gate
and blocks it.
**Priority** P1 · **Complexity** M · **AI** Detector + Tracker
**Future.** Fundamental diagram (flow vs density) per approach road, giving a
measured capacity in vehicles/hour rather than a guessed threshold.

### VEH-006 — Traffic congestion detection
**Description.** High vehicle density with near-zero speed, sustained.
**Business value.** A congested access road is an obstructed emergency route.
**Priority** P1 · **Complexity** S · **AI** Detector + Tracker
**Future.** Queue-tail propagation warning to upstream junctions.

### VEH-007 — Parking occupancy (area-based)
**Description.** Vehicle count within a parking-zone polygon against configured
capacity. Area-based rather than per-space, because the parking areas at this
venue are unmarked open ground.
**Business value.** Live "spaces remaining" for signage and stewarding.
**Priority** P1 · **Complexity** M · **AI** Detector
**Future.** Occupancy by summed vehicle ground-footprint rather than by count,
which is materially more accurate on unmarked ground where vehicles park at
arbitrary angles and spacing.

### VEH-008 — Per-space parking occupancy
**Description.** Operator-drawn per-space polygons; each is occupied or free.
**Business value.** Precise counts; VIP and accessible-bay monitoring.
**Priority** P3 · **Complexity** M · **AI** Detector
**Future.** Only meaningful for marked bays, of which this venue has few. Low
value here, high value for a permanent-venue deployment.

### VEH-009 — Parking full
**Description.** Parking-zone occupancy at or above configured capacity, with a
projected time-to-full derived from current inflow rate.
**Business value.** Diverting arrivals *before* a lot fills is the difference
between an orderly redirect and a blocked access road with no room to turn around.
**Priority** P1 · **Complexity** S · **AI** None (rule over `VEH-007`)
**Future.** Automatic redirect recommendation to the nearest lot with capacity.

### VEH-010 — Illegal / stationary parking
**Description.** A vehicle stationary beyond a threshold inside a zone where
parking is prohibited — emergency routes, pedestrian areas, gate aprons.
Generalizes the prototype's `STATIONARY_OBJECT` rule, which already cools down
per-object rather than globally and can be lifted almost unchanged.
**Business value.** An illegally parked vehicle on an emergency route is a
category-one life-safety failure, and it is invisible to a human operator watching
sixteen tiles.
**Priority** P0 · **Complexity** S · **AI** Detector + Tracker
**Future.** Distinguish "stopped to unload" (short dwell, near a stall) from
"abandoned" (long dwell, anywhere) by dwell and location, to cut nuisance alerts.

### VEH-011 — Vehicle in pedestrian zone
**Description.** Any vehicle class detected inside a `kind=pedestrian_only`
polygon.
**Business value.** Direct pedestrian safety; also catches unauthorized access.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** Whitelisting of authorized service vehicles by **time window rather
than by identity** — a permitted-window rule, not a permit-plate rule, because
reading plates is prohibited.

### VEH-012 — Emergency route clearance
**Description.** Continuous verification that every polygon of
`kind=emergency_route` is clear of vehicles, stalls, and stationary crowds.
**Reports clear/blocked as a persistent state, not as a transient alert.**
**Business value.** The single question the fire officer will ask, at any moment,
about any route. The platform should answer it without a human having to look.
**Priority** P0 · **Complexity** M · **AI** Detector
**Future.** Route-level rollup — a route is blocked if any segment is blocked, and
the dashboard names the blocking segment. Automatic alternate-route computation.

### VEH-013 — Wrong-way vehicle
**Description.** A tracked vehicle moving against the declared direction of a
one-way access road.
**Business value.** Head-on collision risk on narrow single-track access roads.
**Priority** P2 · **Complexity** S · **AI** Detector + Tracker
**Future.** Distinguish reversing (legitimate: low speed, short duration) from
wrong-way travel (sustained).

### VEH-014 — Emergency vehicle recognition
**Description.** Identifying an ambulance, fire appliance, or police vehicle by
appearance.
**Business value.** Automatic route pre-clearance and priority alert routing.
**Priority** P3 · **Complexity** XL · **AI** Custom model
**Future.** **Deferred, with an explicit recommendation against building it.** An
ambulance is a van with livery; visual discrimination is unreliable, and the
failure mode — missing a real emergency vehicle — is severe. The reliable signal
is a **dispatch-system integration or an operator marking** (`OPS-013`), not a
camera. It is specified here so that its absence from v1 is a documented decision
rather than an oversight.

---

## 7. HORSES AND TBOURIDA (`HRS`)

> This is the module that distinguishes MANSOUR Vision from any general crowd
> analytics product, and the module in which the highest-severity events at this
> venue occur. `horse` is a pretrained COCO class, so the *detection* is free.
> The value is entirely in the operational rules built on top of it.

### HRS-001 — Horse detection
**Description.** Detection of `horse` as an anonymous box.
**Business value.** Foundation of the module.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** **Accuracy caveat, stated plainly.** COCO's `horse` images are
predominantly single animals in open, static scenes. A sorba is fifteen horses
abreast, at gallop, in dust, with motion blur, often at dusk. Recall will be
materially worse than COCO's headline numbers suggest. A **site-specific
validation set, captured at this venue, is mandatory before any P0 horse alert is
trusted** (§17, R-02). This may prove to be the one place where a custom-trained
model is unavoidable, and the roadmap reserves budget for it.

### HRS-002 — Horse count per zone
**Description.** Horse count inside each zone polygon, published at 1 Hz.
**Business value.** Arena, waiting-area, and picket-line load.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** Counting by ground-plane footprint to survive the heavy mutual
occlusion of a tightly packed waiting area.

### HRS-003 — Horse rider detection
**Description.** A compositional rule requiring no training: a `person` box whose
lower centroid lies inside a `horse` box, sustained across ≥3 consecutive tracked
frames. Yields ridden vs unridden horses, and rider counts.
**Business value.** Distinguishes a mounted sorba from horses at picket. The input
to `HRS-004`.
**Priority** P1 · **Complexity** S · **AI** Detector + Tracker
**Future.** Handle the handler-leading-horse case (person adjacent, not above) as
a distinct relation, so a led horse is not misread as riderless.

### HRS-004 — Riderless horse detection
**Description.** A `horse` track inside the charge track during an active run,
with no associated `person` per `HRS-003`, sustained beyond a short debounce.
**Business value.** **A riderless horse mid-charge means a rider has fallen at
gallop, in front of fourteen other horses.** This is the most time-critical
medical event the platform can observe. It is detectable today, with no new model,
from two classes we already have — and it is far more reliable than detecting the
fallen rider directly, who will be on the ground, in dust, occluded by the horses
behind.
**Priority** P0 · **Complexity** M · **AI** Detector + Tracker
**Future.** Automatic escalation into the `HRS-017` rider-down protocol.

### HRS-005 — Sorba formation and track state machine
**Description.** Detection of a staged sorba: N ridden horses in a line abreast at
the head of the charge track, N and alignment tolerance configurable. Drives the
track through `cleared → staged → charging → cleared`.
**Business value.** The state machine everything else in this module keys off. It
is what tells the platform that the track is about to become lethal — and
therefore when to arm `HRS-006` at maximum severity and when to disarm the smoke
rule (§4.3).
**Priority** P0 · **Complexity** L · **AI** Detector + Tracker
**Future.** Formation-quality analytics for the organizers and judges — line
straightness, alignment, simultaneity of the volley. A genuinely novel product
capability and a strong commercial differentiator. It is deliberately Phase 4, so
that it never competes for engineering attention with the safety functions that
share its state machine.

### HRS-006 — Charge track (mahrek) incursion
**Description.** Any `person`, `dog`, or vehicle detected inside the charge-track
polygon. Severity is a function of the `HRS-005` track state: `info` when
`cleared`, `warning` when `staged`, **`critical` when `charging`** — and in the
charging state the alert is raised on the *first frame*, with no debounce.
**Business value.** **This is the single most important requirement in this
document.** A person on the track during a charge will be killed. Detection
latency is measured against a horse closing at roughly 15 m/s, which makes the
analytic FPS of track cameras and the end-to-end alert latency budget **safety
parameters, not performance parameters** (§15.4).
**Priority** P0 · **Complexity** M · **AI** Detector
**Future.** A direct hardware interlock to a track-side warning light and audible
alarm, bypassing the operator entirely — because for this specific event the human
in the loop is too slow. Requires a formal safety case; Phase 4.

### HRS-007 — Track clearance verification (go / no-go)
**Description.** A persistent, **positively asserted** state: *the charge track is
clear, and has been continuously observed as clear for T seconds, by cameras whose
health is green and whose calibration is valid.* Not the absence of an alert — the
presence of a verified observation. Degrades to `unknown`, **never to `clear`**,
if any track camera is offline, degraded, or uncalibrated.
**Business value.** Gives the track marshal an instrument to confirm what they can
today confirm only by eye, down a long and dusty track. **The distinction between
"no alert" and "verified clear" is the entire feature.** A system that reports
"clear" when its camera is dead has killed someone.
**Priority** P0 · **Complexity** M · **AI** Detector
**Future.** A marshal-facing physical go/no-go indicator at the start line.

### HRS-008 — Horse arena occupancy
**Description.** Horse and rider count within the arena polygon, against a
configured capacity.
**Business value.** Prevents overloading the arena between runs.
**Priority** P1 · **Complexity** S · **AI** Detector
**Future.** Per-troop occupancy, from staging-area assignment.

### HRS-009 — Horse waiting-area occupancy and density
**Description.** Horse count and ground-plane horse density in the staging and
waiting areas.
**Business value.** A crowded waiting area with stallions in close proximity is an
injury risk to handlers and to the animals. Density here is simultaneously an
animal-welfare metric and a human-safety metric.
**Priority** P1 · **Complexity** M · **AI** Detector
**Future.** Horse-to-horse minimum-separation monitoring.

### HRS-010 — Horse entry and exit counting
**Description.** Directional line counts for `horse`, and separately for ridden
horses, at arena, waiting area, and venue gates.
**Business value.** Reconciles how many animals are on site — a welfare and
veterinary-readiness question, and one the authorities may ask.
**Priority** P1 · **Complexity** S · **AI** Detector + Tracker
**Future.** Reconciliation against the registered troop manifest.

### HRS-011 — Horse movement and charge detection
**Description.** Ground-plane speed of horse tracks. A sustained multi-horse
high-speed vector down the track axis *is* a charge in progress, and drives the
`charging` state of `HRS-005`.
**Business value.** Automatic, sensor-free detection of when a run starts and
ends. No operator has to press a button, and no schedule has to be accurate.
**Priority** P0 · **Complexity** M · **AI** Detector + Tracker
**Future.** Run duration, peak speed, and runs per troop — the raw material of
`HRS-018`.

### HRS-012 — Horse density
**Description.** Horses per 100 m² per zone, ground-plane.
**Business value.** Comparable across zones and cameras, unlike a raw count.
**Priority** P2 · **Complexity** S · **AI** Detector
**Future.** Combined horse-and-person density for mixed zones, weighted by
footprint — one horse occupies the space, and the risk, of several people.

### HRS-013 — Horse picket line / horse parking occupancy
**Description.** Occupancy of the tethering and rest areas.
**Business value.** Capacity management for arriving troops; welfare (shade and
water-station load).
**Priority** P2 · **Complexity** S · **AI** Detector
**Future.** Dwell time per picket area by Little's Law, indicating rest adequacy.

### HRS-014 — Horse trailer detection
**Description.** Recognition of horse transport trailers at the venue gate.
**Business value.** Arrival logistics and gate routing.
**Priority** P3 · **Complexity** XL · **AI** Custom model
**Future.** Not a COCO class; deferred to the custom-dataset track. In v1 a
trailer detects as `truck`, which is sufficient for the access-lane rules that
actually matter.

### HRS-015 — Horse–crowd proximity (buffer breach)
**Description.** A `horse` whose ground-plane position falls within a configured
buffer of the spectator polygon, or a `person` within a buffer of a horse outside
the designated interaction zones.
**Business value.** Mixed horse-and-pedestrian space is the defining hazard of
this venue. A 500 kg animal at speed adjacent to a dense crowd is the scenario
that must never be allowed to develop unobserved.
**Priority** P0 · **Complexity** M · **AI** Detector
**Future.** Directional risk weighting — a horse moving *toward* the crowd is a
different event from one moving away at the same distance.

### HRS-016 — Horse in restricted area
**Description.** `horse` inside any `kind=restricted` polygon. A `kind`-driven
rule per ADR 0003; no horse-specific machinery required.
**Business value.** Loose or misrouted animals in the market, food court, or
prayer area.
**Priority** P1 · **Complexity** S · **AI** Detector
**Future.** Loose-horse detection — a horse outside all permitted zones, unridden
and unled — as a distinct and higher-severity event.

### HRS-017 — Rider-down protocol
**Description.** An orchestrated response, not a detection. On `HRS-004`, or a
high-confidence `SID` event on the track, the platform holds the track at `no-go`,
pushes the incident to the medical channel with a snapshot and the preceding 30
seconds of video, and requires an explicit operator clear-down before `HRS-007`
can return to `verified clear`.
**Business value.** Converts a detection into a response. The value of seeing a
fall lies entirely in what happens in the next twenty seconds.
**Priority** P1 · **Complexity** M · **AI** None (orchestration)
**Future.** Direct integration with the on-site medical team's dispatch system.

### HRS-018 — Tbourida event analytics
**Description.** Runs per hour, run duration, inter-run interval, horses per
sorba, track utilization, and spectator occupancy correlated against the run
schedule.
**Business value.** The organizer's post-event report and next year's schedule
design. Also the evidence base for a question nobody can currently answer: *does
spectator density peak dangerously in the minutes before each run?*
**Priority** P2 · **Complexity** M · **AI** None (aggregation)
**Future.** Formation-quality metrics from `HRS-005`; multi-year comparison.

---

## 8. EVENT OPERATIONS (`OPS`)

> These features do not introduce new detection. They are **zone-typed
> compositions** of `PPL`, `VEH`, and `HRS` primitives, per ADR 0003. Their value
> is that they present the platform in the vocabulary of an event operations
> centre rather than in the vocabulary of computer vision.

### OPS-001 — Entrance operations
**Description.** Per-gate: inflow rate, queue length, waiting time, upstream
density, lanes open, and a computed *gate service rate*. Rolled up to a venue-wide
ingress view showing which gate is the constraint.
**Business value.** Ingress is where crowd incidents concentrate. This is the
operations centre's primary morning screen.
**Priority** P0 · **Complexity** M · **AI** None (composition)
**Future.** Projected ingress completion time against the programme; automatic
recommendation to open a lane when projected waiting time exceeds a target.

### OPS-002 — Exit and egress operations
**Description.** Per-gate outflow, egress capacity in persons/minute, persons
remaining in the venue, and a live estimated time to clear.
**Business value.** Egress is the other half of the risk, and the only one that
matters during an evacuation.
**Priority** P0 · **Complexity** M · **AI** None (composition)
**Future.** Evacuation-mode dashboard: all lines become exits, all thresholds
change, and the display switches from "how many are here" to "how many remain and
how long until zero."

### OPS-003 — Gate balance
**Description.** Distribution of ingress and egress load across gates, flagging
imbalance beyond a threshold.
**Business value.** An overloaded gate beside an empty one is a stewarding
problem with a five-minute fix, and it is invisible from any single camera.
**Priority** P1 · **Complexity** S · **AI** None (composition)
**Future.** Signage integration to actively rebalance arrivals.

### OPS-004 — Parking operations
**Description.** Per-lot occupancy, capacity, inflow, time-to-full, and a
venue-wide rollup with remaining capacity.
**Business value.** See `VEH-009`. Parking failures propagate onto access roads
and become emergency-access failures.
**Priority** P1 · **Complexity** M · **AI** None (composition)
**Future.** Coordinated overflow routing.

### OPS-005 — Food court operations
**Description.** Occupancy, density, queue lengths per stall cluster, dwell time
by Little's Law.
**Business value.** Commercial (vendor placement, revenue-per-m²) and safety
(the food court is typically the densest non-performance area).
**Priority** P2 · **Complexity** S · **AI** None (composition)
**Future.** Per-vendor footfall for commercial reporting to concession-holders,
which is a directly monetizable output.

### OPS-006 — Market operations
**Description.** Aisle density, aisle-level flow and counterflow, bottleneck
detection between stalls.
**Business value.** Market aisles are narrow, bidirectional, and obstructed by
stalls — the archetypal counterflow bottleneck.
**Priority** P2 · **Complexity** M · **AI** None (composition)
**Future.** Detection of stall encroachment into the aisle, which is what creates
the bottleneck in the first place — a static-obstruction change-detection problem,
not an object-detection problem.

### OPS-007 — Prayer area operations
**Description.** Occupancy and density against capacity, with **schedule-aware
thresholds** bound to the five daily prayer times and to Friday prayer.
**Business value.** The prayer area fills and empties abruptly, on a known
schedule, five times a day. Static thresholds would produce ten guaranteed false
criticals per day, every day, and would train operators to ignore the alert
channel. This feature exists primarily to *prevent* alerts, which is an
underrated form of value.
**Priority** P1 · **Complexity** M · **AI** None (composition + §4.3 arming)
**Future.** Predictive pre-positioning of stewards ahead of each prayer, from the
learned fill curve.

### OPS-008 — VIP area operations
**Description.** Occupancy, restricted-access breach detection (`person` in a
`kind=vip` polygon outside permitted windows), and route clearance to the VIP
area.
**Business value.** Protocol and security.
**Priority** P2 · **Complexity** S · **AI** None (composition)
**Future.** None planned. **Note:** access control here is *zone-and-time* based,
never identity based. The platform reports that *someone* is in the VIP area
outside hours. Determining *who* is a human security function, not a software one.

### OPS-009 — Medical area operations
**Description.** Occupancy of the medical tent and its approaches; queue length at
triage; verification that the medical access route is clear (`VEH-012`).
**Business value.** A medical facility that cannot be reached is not a medical
facility. Load on triage is a leading indicator of an emerging mass-casualty
situation.
**Priority** P1 · **Complexity** S · **AI** None (composition)
**Future.** Correlation of triage load against zone density, which would give the
first quantitative evidence linking crowd density to injury rate at this event.

### OPS-010 — Emergency route monitoring
**Description.** Continuous clear/blocked state per route, per segment, with the
blocking object class and its dwell time. State — not alert.
**Business value.** The fire officer's standing question, answered continuously.
**Priority** P0 · **Complexity** M · **AI** None (composition of `VEH-012`)
**Future.** Alternate-route computation; automatic notification of the blocking
vehicle's owner via the stewarding channel.

### OPS-011 — Restricted zone monitoring
**Description.** Any intrusion by `person`, `vehicle`, or `horse` into any
`kind=restricted` polygon, with per-zone arming schedules.
**Business value.** Back-of-house, plant, generator, and staging areas.
**Priority** P1 · **Complexity** S · **AI** None (composition)
**Future.** Learned-baseline arming, so a zone that legitimately has staff
present during setup does not alarm continuously during setup.

### OPS-012 — Security checkpoint operations
**Description.** Per-checkpoint throughput, queue length, waiting time, lanes
open, and service rate. Identical machinery to `OPS-001`; different zone type.
**Business value.** A checkpoint is a deliberate bottleneck. Knowing its service
rate is the only way to size it.
**Priority** P1 · **Complexity** S · **AI** None (composition)
**Future.** Screening-rate anomaly detection — a lane whose service rate suddenly
doubles is a lane that has stopped screening properly.

### OPS-013 — Operator-marked incidents and manual overrides
**Description.** A first-class, non-vision input path: an operator marks an
incident, an emergency vehicle arrival, a route closure, or a manual zone state.
Manual state takes precedence over inferred state, is timestamped, attributed, and
written to the audit log.
**Business value.** Every automated system in a command centre must be
overridable by the person who can see out of the window. It is also how
`VEH-014` (emergency vehicle recognition) is satisfied *without building
`VEH-014`.*
**Priority** P0 · **Complexity** S · **AI** Non-vision
**Future.** Mobile steward app, so ground staff can mark incidents where they
stand.

### OPS-014 — Evacuation readiness
**Description.** A single composite state: for the current venue occupancy, are
all egress routes clear, is total egress capacity sufficient, and what is the
projected time to clear? Recomputed continuously.
**Business value.** Turns evacuation planning from a document written six months
ago into a live instrument. Answers, at any instant, *"if we called it now, how
long?"*
**Priority** P1 · **Complexity** L · **AI** None (composition)
**Future.** Per-zone evacuation routing that accounts for the current density
field rather than the static plan; the crowd does not evacuate along the lines a
planner drew.

---

## 9. SECURITY INCIDENT DETECTION (`SID`)

> **This module replaces "fight detection."** It does not classify the conduct of
> any individual. It detects **anonymous crowd anomalies** — deviations in the
> aggregate motion field and density field — and raises a single, confidence-scored
> **Potential Security Incident** for an operator to verify on live video.
>
> The system's assertion is *"something anomalous is happening at these
> coordinates, with this confidence, of this character."* The system never asserts
> that a person is fighting, stealing, or behaving suspiciously. That determination
> is made by a human being looking at a video feed, which is where it belongs —
> legally, ethically, and practically, since the false-positive rate of automated
> conduct classification in dense crowds makes it operationally worthless anyway.
>
> Every constituent signal below is computed from aggregate optical flow and
> aggregate density. **None requires identifying, tracking, or characterising a
> person**, and all remain fully compliant with ADR 0004.

### SID-001 — Signal: sudden running crowd
**Description.** Abrupt, sustained increase in mean flow-field speed across a
zone, beyond its learned baseline for that time of day.
**Priority** P1 · **Complexity** M · **AI** Flow
**Future.** Discriminate a crowd running *toward* something (an attraction, a
performance starting) from running *away* (`SID-002`) by pairing with divergence.

### SID-002 — Signal: rapid crowd dispersion
**Description.** Strongly positive divergence of the flow field — people moving
away from a common point (`PPL-018`).
**Priority** P0 · **Complexity** M · **AI** Flow
**Future.** Localize the divergence source to a ground coordinate and slew a PTZ
camera to it automatically. **This is the highest-value signal in the module:**
whatever happened — a fall, an altercation, a collapse, a fire — the crowd's
reaction is visible even when the cause is completely occluded.

### SID-003 — Signal: sudden crowd convergence
**Description.** Strongly negative divergence — people converging on a point.
**Priority** P1 · **Complexity** M · **AI** Flow
**Future.** Distinguish a benign attraction (slow convergence, stable density)
from an incident gathering (fast convergence, rising density).

### SID-004 — Signal: panic movement
**Description.** High speed, low directional coherence, high acceleration variance
— movement that is fast but not going anywhere together. Distinct from `SID-001`,
where a running crowd is fast *and* coherent.
**Priority** P1 · **Complexity** L · **AI** Flow
**Future.** Threshold validation against recorded footage of real crowd surges;
until then this signal contributes to the composite score but does not alarm alone.

### SID-005 — Signal: abnormal motion intensity
**Description.** Total kinetic energy of the flow field within a zone, against its
learned per-zone, per-time-of-day baseline.
**Priority** P2 · **Complexity** M · **AI** Flow
**Future.** Separate baselines per programme state, since motion intensity during
a tbourida run is legitimately extreme.

### SID-006 — Signal: crowd pushing / compression
**Description.** `PPL-012` turbulence at high density: oscillating, incoherent
velocity within a crowd that is not translating. The physical signature of people
pressing against each other.
**Priority** P0 · **Complexity** L · **AI** Flow
**Future.** The crush-risk indicator. Must not ship with unvalidated thresholds
(§17, R-03).

### SID-007 — Signal: unusual stationary crowd
**Description.** `PPL-017` — a dense, stationary cluster in a transit zone,
persisting beyond its learned baseline.
**Priority** P2 · **Complexity** M · **AI** Detector + Flow
**Future.** Growth-rate ranking, so a gathering doubling every minute outranks a
static one.

### SID-008 — Signal: queue collapse
**Description.** `PPL-015` — loss of queue coherence with sustained or rising
density.
**Priority** P1 · **Complexity** L · **AI** Flow
**Future.** Discriminate collapse-from-surge (pressure from behind) from
collapse-from-blockage (the gate stopped), which demand opposite interventions.

### SID-009 — Signal: restricted-area intrusion
**Description.** `OPS-011` / `HRS-006` — presence where presence is prohibited.
The one `SID` signal that is deterministic rather than statistical, and therefore
the one that can alarm alone with high confidence.
**Priority** P0 · **Complexity** S · **AI** Detector
**Future.** —

### SID-010 — Signal: person falling
**Description.** `PPL-022`. Contributes to the composite score in sparse and
moderate zones. Explicitly down-weighted at high density, where it does not work
and where `SID-002` and `SID-006` do.
**Priority** P2 · **Complexity** L · **AI** Detector + Tracker
**Future.** See `PPL-022`.

### SID-011 — Composite: Potential Security Incident
**Description.** A fusion layer over `SID-001`…`SID-010`. Raises **one**
operator-facing alert — *Potential Security Incident* — carrying:
a **confidence score**, a **ground coordinate**, the **contributing signals**
ranked by weight, the **camera** to view it on, and a **snapshot**. It never
carries a label describing what anyone was doing.
**Business value.** One alert channel instead of ten. Confidence lets the operator
triage. Contributing signals let the operator understand *why* the system is
pointing there, which is what makes an operator trust it — or correctly dismiss
it. And the whole thing is anonymous, which keeps the platform's central promise
intact under the exact conditions where a competitor's product would break it.
**Priority** P0 · **Complexity** L · **AI** Flow (fusion)
**Future.** Operator feedback loop: every confirm/dismiss is labelled training
data for the fusion weights. **This is the only learning loop in the platform,
and it learns from crowd-motion statistics and operator judgements — never from
imagery of people.** Per-zone, per-programme-state weight adaptation. Phase 4.

---

## 10. ALERT CATALOGUE (`ALR`)

Alert **severities**: `info` (log, no interrupt) · `warning` (operator queue) ·
`critical` (interrupt, audible, requires acknowledgement) · `emergency`
(interrupt, audible, auto-escalates to supervisor and to the relevant channel if
not acknowledged within the escalation window).

Every alert carries the fields specified in `docs/architecture/data-model.md`:
id, type, severity, camera, zone, timestamp, title, description, snapshot,
status, assigned operator, `dedup_key`, and context.

| ID | Alert | Sev | Source | Armed when | Notes |
|---|---|---|---|---|---|
| ALR-01 | **Track incursion — charging** | emergency | HRS-006 | track `charging` | First frame, no debounce. The highest-severity alert in the platform. |
| ALR-02 | **Riderless horse on track** | emergency | HRS-004 | track `charging` | Triggers `HRS-017` rider-down protocol. |
| ALR-03 | Track incursion — staged | critical | HRS-006 | track `staged` | |
| ALR-04 | Emergency exit blocked | emergency | VEH-012 | always | Persistent state; alert on transition to blocked. |
| ALR-05 | Emergency route blocked | critical | OPS-010 | always | |
| ALR-06 | **Crowd crush risk** (density × turbulence) | emergency | SID-006 | calibrated zones only | Suppressed on uncalibrated cameras — see §4.1. |
| ALR-07 | Critical crowd density | critical | PPL-007 | per-zone schedule | LOS band `Critical`. |
| ALR-08 | High crowd density | warning | PPL-007 | per-zone schedule | LOS band `High`. |
| ALR-09 | **Potential security incident** | critical | SID-011 | always | Confidence-scored. Operator verifies on video. |
| ALR-10 | Rapid crowd dispersion | critical | SID-002 | always | Also feeds ALR-09. |
| ALR-11 | Running crowd | warning | SID-001 | not during a run | Suppressed on the track during `charging`. |
| ALR-12 | Queue collapse | critical | PPL-015 | gate/checkpoint zones | |
| ALR-13 | Bottleneck forming | warning | PPL-016 | always | |
| ALR-14 | Counterflow detected | warning | PPL-011 | one-way zones | |
| ALR-15 | Blocked entrance | critical | OPS-001 | ingress window | High density + throughput ≈ 0. |
| ALR-16 | Horse–crowd buffer breach | critical | HRS-015 | always | |
| ALR-17 | Horse in restricted area | warning | HRS-016 | always | |
| ALR-18 | Loose horse | critical | HRS-016 | always | Unridden, unled, outside all permitted zones. |
| ALR-19 | Vehicle in pedestrian zone | critical | VEH-011 | always | |
| ALR-20 | Illegal / abandoned vehicle | warning | VEH-010 | per-zone | Escalates to critical on an emergency route. |
| ALR-21 | Abandoned object | warning | *(see below)* | per-zone | Static-region change detection; **not object detection**. |
| ALR-22 | Traffic congestion | warning | VEH-006 | approach roads | |
| ALR-23 | Wrong-way vehicle | warning | VEH-013 | one-way roads | |
| ALR-24 | Parking full | info | VEH-009 | always | Escalates to warning at projected-full minus 15 min. |
| ALR-25 | Restricted area occupied | warning | OPS-011 | per-zone schedule | |
| ALR-26 | VIP area breach | warning | OPS-008 | outside permitted window | |
| ALR-27 | Queue too long | warning | PPL-013 | gate/checkpoint | Threshold in waiting-time, not persons. |
| ALR-28 | Lost person advisory | info | PPL-021 | always | Never states age. Operator verifies. |
| ALR-29 | **Smoke detected** | critical | *(custom model, Ph. 3)* | **contextually armed** | Disarmed on the track and its downwind cone during a scheduled run (§4.3). |
| ALR-30 | **Fire detected** | emergency | *(custom model, Ph. 3)* | contextually armed | Same arming as ALR-29. Never suppressed outside the track zone. |
| ALR-31 | Camera offline | critical | CAM-001 | always | Keyed on **frame staleness**, not handle state. |
| ALR-32 | Camera tampering | critical | CAM-008 | always | Covered, moved, defocused, or sprayed. |
| ALR-33 | Video loss / decode failure | critical | CAM-002 | always | |
| ALR-34 | Low FPS / analytic starvation | warning | CAM-004 | always | The system is no longer seeing what it claims to. |
| ALR-35 | Low detection confidence | warning | CAM-011 | always | Typically nightfall or lens contamination. |
| ALR-36 | Camera uncalibrated | warning | CAM-012 | always | Crush-risk alerts auto-suppressed for that camera. |
| ALR-37 | AI inference service degraded | critical | SYS-007 | always | |
| ALR-38 | GPU overloaded | warning | SYS-002 | always | Analytic FPS is being dropped to cope. |
| ALR-39 | Storage almost full | warning | SYS-004 | always | Escalates to critical at 95%. |
| ALR-40 | Database / Redis unavailable | critical | SYS-005/6 | always | Detection continues; history is accruing a gap. |
| ALR-41 | Event bus lag | warning | SYS-008 | always | Consumers falling behind producers. |
| ALR-42 | Alert storm suppression engaged | info | §15.2 | always | The platform announces its own suppression. Never silent. |
| ALR-43 | Rule disarmed by schedule | info | §4.3 | always | Every automatic disarm is visible and audited. |

### On ALR-21 (abandoned object) and ALR-29/30 (fire and smoke)

**Abandoned object is not an object-detection problem.** No detector has a class
for "unattended bag." It is a *static-region change-detection* problem: a region
of the background that was not there ten minutes ago, is not moving, and has no
person persistently adjacent to it. This is classical computer vision, needs no
training, and — critically — needs **aggressive zone gating**. In a market full of
crates, sacks, and stall furniture, an ungated abandoned-object rule produces
hundreds of alerts an hour. It is specified for gates, checkpoints, the prayer
area, and the medical approach; nowhere else.

**Fire and smoke require a custom model** and are the one place where a custom
model is clearly worth its cost. They are Phase 3 and are governed entirely by the
contextual-arming machinery of §4.3, without which they are worse than useless at
this venue.

---

## 11. NON-VISION INPUTS

The platform's value comes substantially from fusing vision with context that is
not in any camera. These are first-class inputs, with schemas and health checks,
not afterthoughts.

| Input | Source | Feeds | Priority |
|---|---|---|---|
| **Event programme / schedule** | Organizer, ingested or entered | §4.3 contextual arming, `HRS-005`, `OPS-007`, all baselines | **P0** |
| Zone capacities and LOS thresholds | Event safety officer, signed off | Every density and occupancy alert | **P0** |
| Camera calibration (homography) | Site survey | Density, speed, all ground-plane metrics | **P0** |
| Operator marks and overrides | `OPS-013` | Emergency vehicles, incidents, route closures | **P0** |
| Weather (wind, rain, temperature) | Weather API | Dust/visibility expectation, crowd-behaviour baselines, horse welfare | P2 |
| Prayer times | Computed from date and location | `OPS-007` arming | P1 |
| Medical / dispatch system | Integration | `HRS-017`, `OPS-009` | P3 |
| Panic buttons / steward radio | Integration | Manual incident raise | P3 |

**Assumption A2 (§2.5) is load-bearing.** If no machine-readable programme is
available, contextual arming degrades to manual operator arming, which is
workable but adds an operator action before every tbourida run. This must be
confirmed early because it changes the operator UI.

---

## 12. CAMERA HEALTH (`CAM`)

> A crowd-safety platform that reports "clear" from a dead camera is more
> dangerous than no platform at all. Camera health is therefore not an
> administrative feature — it is a **precondition of every safety assertion the
> system makes**. `HRS-007` degrades to `unknown` on any camera-health failure,
> and it degrades to `unknown`, never to `clear`.

### CAM-001 — Camera online / offline
**Description.** Keyed on **frame staleness**, not on whether the capture handle
is open. A dead network stream leaves `read()` blocking for tens of seconds while
the handle still looks healthy — the prototype already gets this right, and the
behaviour is carried forward verbatim.
**Business value.** The most common failure in any CCTV deployment, and the one
most often detected late.
**Priority** P0 · **Complexity** S · **AI** None
**Future.** Distinguish network loss from camera power loss by ARP/ICMP probe,
which tells the technician what to carry to the pole.

### CAM-002 — Video loss and decode failure
**Description.** Stream connected but frames undecodable or corrupt.
**Priority** P0 · **Complexity** S · **AI** None
**Future.** Per-codec error taxonomy.

### CAM-003 — Stream latency
**Description.** End-to-end wall-clock age of the frame currently being analysed.
**Business value.** For `HRS-006`, latency is a safety parameter (§15.4). A
correct alert that arrives two seconds late has not saved anyone.
**Priority** P0 · **Complexity** M · **AI** None
**Future.** NTP-synchronized camera clocks to separate network latency from
pipeline latency.

### CAM-004 — Analytic FPS
**Description.** The rate at which frames are actually *analysed*, distinct from
the camera's native FPS. Under load the worker sheds frames; this metric is what
makes that shedding visible instead of silent.
**Business value.** A camera streaming at 25 FPS but analysed at 1 FPS is
effectively blind to a horse at 15 m/s. The dashboard must say so.
**Priority** P0 · **Complexity** S · **AI** None
**Future.** Per-camera minimum analytic FPS as a hard SLO, with load shed
preferentially from low-priority cameras so that track cameras never starve.

### CAM-005 — Bitrate and stream quality
**Priority** P2 · **Complexity** S · **AI** None
**Description / value.** Detects a camera that has silently renegotiated to a
lower bitrate, which degrades small-object recall before it degrades anything a
human would notice on a monitor.
**Future.** Correlate bitrate drops with detection-confidence drops (`CAM-011`).

### CAM-006 — Recording state and storage
**Description.** Whether the camera is recording, to where, and the retention
headroom remaining.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Per-camera retention policy driven by zone risk level.

### CAM-007 — Connection and protocol health
**Description.** Reconnect count, time since last reconnect, RTSP/ONVIF error
codes, packet loss.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Flapping detection — a camera reconnecting every 90 seconds is worse
than one cleanly offline, and it currently reports as "online."

### CAM-008 — Camera tampering
**Description.** Four distinct signatures, all classical CV, no model:
**covered** (sudden global luminance/entropy collapse), **moved** (persistent
scene-registration shift against a reference), **defocused** (sustained loss of
high-frequency energy), **sprayed/obscured** (persistent localized entropy loss).
**Business value.** A tampered camera is either a fault or an attack; both need a
person dispatched. Camera movement additionally **invalidates the homography**,
so `CAM-008` automatically invalidates `CAM-012` and suppresses that camera's
crush-risk alerts. **This coupling is essential and easy to miss.**
**Priority** P1 · **Complexity** M · **AI** None
**Future.** Automatic re-calibration proposal after a detected move.

### CAM-009 — GPU worker assignment
**Description.** Which `vision-worker` owns this camera, and its health.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Automatic reassignment on worker loss, with track cameras
re-homed first.

### CAM-010 — Inference health per camera
**Description.** Inference latency, queue depth, frames dropped, model version.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Per-camera model selection — a heavier model on the track cameras,
a lighter one on the car park.

### CAM-011 — Detection confidence health
**Description.** Rolling distribution of detection confidences per camera against
its own daytime baseline. A sustained collapse in mean confidence means the
camera can no longer see: nightfall, fog, dust, rain, a dirty lens, or a
contaminated dome.
**Business value.** **This is how the platform avoids lying at night.** Counts do
not simply become noisier as light fails — they become *systematically low*, and a
naive dashboard renders that as "the crowd went home." The correct behaviour is to
degrade the camera's health, widen the occupancy confidence interval, and say so.
**Priority** P0 · **Complexity** M · **AI** None (statistics over detector output)
**Future.** Automatic exposure/gain control via ONVIF; a low-light-tuned model
variant selected by measured illumination.

### CAM-012 — Calibration validity
**Description.** Whether a valid, current homography exists for this camera; when
it was last verified; and whether `CAM-008` has invalidated it.
**Business value.** Gates every ground-plane metric. An uncalibrated camera reports
*uncalibrated*, is visibly flagged, and cannot raise a crush-risk alert (§4.1).
**Priority** P0 · **Complexity** M · **AI** None
**Future.** Continuous self-check against known static ground features; automatic
drift correction.

### CAM-013 — Temperature (where supported)
**Description.** Camera housing temperature via ONVIF, where the device exposes it.
**Priority** P3 · **Complexity** S · **AI** None
**Future.** Thermal shutdown prediction for sun-exposed poles in August.

---

## 13. SYSTEM HEALTH (`SYS`)

### SYS-001 — CPU utilization (per host, per service)
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Correlate with analytic FPS to attribute shedding to a cause.

### SYS-002 — GPU utilization, memory, temperature, and throttling
**Description.** Per-GPU utilization, VRAM, temperature, and — importantly —
whether the GPU is thermally or power throttled.
**Business value.** A throttled GPU sheds analytic FPS silently. In an outdoor
command tent in summer, this is not hypothetical.
**Priority** P0 · **Complexity** S · **AI** None
**Future.** Predictive shedding: reduce low-priority camera FPS *before* the GPU
throttles, so the shed is chosen rather than imposed.

### SYS-003 — RAM and swap
**Priority** P1 · **Complexity** S · **AI** None
**Future.** OOM-risk projection per worker.

### SYS-004 — Disk and storage
**Description.** Free space, write throughput, and projected time-to-full for
recordings, snapshots, and the database.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Automatic retention tightening under pressure, with audit entry.

### SYS-005 — Database health
**Description.** Connection-pool saturation, replication lag, slow-query rate,
hypertable chunk health.
**Priority** P1 · **Complexity** M · **AI** None
**Future.** Read-replica routing for the reporting workload.

### SYS-006 — Redis / event-bus health
**Description.** Stream length, memory, consumer-group lag, pending-entry count.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Automatic stream trimming under memory pressure, with audit entry.

### SYS-007 — Inference worker health
**Description.** Per-worker: cameras assigned, aggregate analytic FPS, inference
latency percentiles, model version, execution provider in use.
**Business value.** The capacity picture. Answers "can I add ten more cameras?"
with a measurement rather than an opinion.
**Priority** P0 · **Complexity** M · **AI** None
**Future.** Automatic camera rebalancing across workers.

### SYS-008 — Event-bus lag
**Description.** Producer-to-consumer lag per stream and per consumer group.
**Business value.** Lag means the dashboard is showing the past. An operator must
know that.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Backpressure signalling to workers.

### SYS-009 — API latency
**Description.** Request-latency percentiles (p50/p95/p99) per endpoint, error
rates by class.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Per-endpoint SLOs with error budgets.

### SYS-010 — WebSocket connections and active operators
**Description.** Live connection count, message-delivery lag, reconnect rate; the
set of operators currently signed in and their assigned zones.
**Business value.** Answers "is anyone actually watching the north gate right now?"
— which, during an incident, is the only question that matters.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Alert if a `critical`-severity zone has no operator assigned.

### SYS-011 — Platform observability posture
**Description.** A single composite: what fraction of the venue is currently
observed by a healthy, calibrated camera? Which zones are unobserved?
**Business value.** **The most honest number the platform can display.** No other
metric tells the event director what the system cannot see. Directly gates the
credibility of the whole dashboard.
**Priority** P0 · **Complexity** M · **AI** None
**Future.** Coverage map overlay showing observed, degraded, and blind ground area.

### SYS-012 — Audit-log integrity
**Description.** Verification that the append-only constraint on `audit_logs`
holds, and that no gap exists in the sequence.
**Priority** P1 · **Complexity** S · **AI** None
**Future.** Periodic hash-chain anchoring, so tampering is detectable even by a
database administrator.

---

## 14. ANALYTICS AND KPIs (`KPI`)

All KPIs derive from the continuous aggregates in
`docs/architecture/data-model.md`. None requires new detection. All are anonymous.

| ID | KPI | Description | Priority | Complexity |
|---|---|---|---|---|
| KPI-01 | Hourly visitors | Entries per hour, per gate and venue-wide | P0 | S |
| KPI-02 | Daily visitors | Total entries per day. **A count of entries, not of persons** — the system cannot know about re-entry, and does not try | P0 | S |
| KPI-03 | Peak occupancy | Max concurrent occupancy, per zone and venue-wide, with timestamp | P0 | S |
| KPI-04 | Peak hour | Hour of maximum inflow and of maximum occupancy — usually different, and the difference is operationally interesting | P1 | S |
| KPI-05 | Peak zone | Zone with the highest density-hours over a window | P1 | S |
| KPI-06 | Average occupancy | Time-weighted mean occupancy per zone | P1 | S |
| KPI-07 | Average queue time | Little's Law mean per queue, with suppression when out of steady state | P1 | M |
| KPI-08 | Gate service rate | Persons/min/lane, per gate, per hour | P1 | S |
| KPI-09 | Evacuation-time estimate | Live: occupancy ÷ Σ egress capacity, adjusted for blocked routes | P1 | M |
| KPI-10 | Vehicle statistics | Counts by class, by gate, by hour; parking utilization curves | P1 | S |
| KPI-11 | Horse statistics | Horses on site, by zone and by hour; entries and exits; arena utilization | P1 | S |
| KPI-12 | Tbourida statistics | Runs, run duration, inter-run interval, horses per sorba, track utilization | P2 | M |
| KPI-13 | Alert statistics | Alerts by type, severity, zone, hour; **mean time to acknowledge; mean time to resolve** | P0 | S |
| KPI-14 | **False-positive rate per rule** | Fraction of alerts dismissed by an operator, per rule, per zone | P0 | M |
| KPI-15 | Camera uptime | Availability per camera; mean time between failures; time spent uncalibrated or degraded | P0 | S |
| KPI-16 | Observability coverage | `SYS-011` over time: what fraction of the venue was actually observed, per hour | P0 | M |
| KPI-17 | Occupancy reconciliation residual | End-of-day counting error per gate (ADR 0006). **The platform's own accuracy, measured** | P1 | M |
| KPI-18 | Operator activity | Alerts acknowledged and resolved per operator; response latency distribution | P2 | S |
| KPI-19 | Detection confidence trend | Mean confidence per camera per hour; the objective record of when the system could see | P1 | S |
| KPI-20 | Density-hours by zone | ∫ density dt — the exposure metric that correlates with incident rate | P2 | M |

### On KPI-14 and KPI-18

**`KPI-14` (false-positive rate) is a P0 KPI and it is aimed at us, not at the
customer.** A rule with a 90% dismissal rate is not a feature; it is a source of
alarm fatigue that degrades every other alert in the system. We must measure it
from day one, publish it, and be willing to disable our own rules on the evidence.

**`KPI-18` (operator activity) is deliberately scoped narrowly.** It measures
alert-response latency, which is an operational-readiness metric. It is **not** a
surveillance tool for staff performance management, it must not be presented as
one, and per-operator data is visible only to a supervisor role. A platform that
refuses to profile visitors and then profiles its own staff has learned nothing.

---

## 15. CROSS-CUTTING REQUIREMENTS

### 15.1 The alert system must be trustworthy before it is comprehensive

An alert channel that cries wolf is worse than silence, because it trains
operators to dismiss without looking — including the one alert that mattered. The
following are hard requirements on every rule in §10:

1. **Every rule has a measured false-positive rate** (`KPI-14`), reviewed weekly
   during the event and at every release.
2. **Every rule has a dismissal path** with a one-click reason code, feeding
   `KPI-14`.
3. **No rule ships to production with unvalidated thresholds.** Thresholds derived
   from literature are placeholders until validated against footage from this
   venue.
4. **A rule whose FP rate exceeds its budget is automatically demoted** in
   severity and flagged for review. The platform polices its own noise.

### 15.2 Alert storm suppression

Correlated conditions produce correlated alerts: one blocked gate raises blocked
entrance, queue too long, bottleneck, high density, and counterflow — five alerts,
one problem. Rules are grouped into **incident clusters** by zone and time window;
the cluster raises **one** parent alert with its contributing rules attached.

When suppression engages, the platform says so (`ALR-42`). **It never suppresses
silently**, and it never suppresses `emergency` severity.

### 15.3 Contextual arming state is always visible

Per §4.3. Every automatic arm and disarm writes to the audit log with its
triggering context. The operator UI shows, at all times, which rules are currently
disarmed and why, with one-click manual re-arming. `emergency`-severity rules
outside the charge-track smoke exception cannot be disarmed by schedule at all.

### 15.4 Latency budgets are safety parameters

For `HRS-006` (track incursion), a horse closes at ~15 m/s. Every 100 ms of
end-to-end latency is 1.5 metres. The budget, glass-to-operator:

| Stage | Budget |
|---|---|
| Capture + decode | ≤ 120 ms |
| Inference (track cameras, priority queue) | ≤ 60 ms |
| Rule evaluation + publish | ≤ 20 ms |
| Bus + alert engine | ≤ 50 ms |
| WebSocket to operator UI, rendered | ≤ 150 ms |
| **Total (p99)** | **≤ 400 ms** |

Track cameras run at an elevated analytic FPS, are pinned to a dedicated worker,
and are **never** subject to load-shed. This budget is a testable requirement, not
an aspiration, and it is the reason `HRS-006`'s long-term answer is a hardware
interlock (a human operator's reaction time alone exceeds the entire budget above).

### 15.5 Degradation is explicit, never silent

Every metric the platform displays carries provenance: is the camera healthy, is
it calibrated, how old is the underlying observation, what is the confidence?

The prohibited failure mode, in every case, is **a number that looks authoritative
and means nothing**. Uncalibrated density renders as "uncalibrated," not as a
plausible figure. A stale occupancy renders as stale. A track camera that is down
makes the track `unknown`, not `clear`. This principle is worth more to a
government stakeholder than any individual feature in this document.

---

## 16. ROADMAP

Phases are defined by **what the platform can be trusted to do**, not by feature
count. Priorities in §5–§14 map to phases as follows.

### Phase 1 — Prototype *(status: substantially complete in `mar-vision/`)*

**Goal:** prove the pipeline end to end on one camera.
Single camera, person and vehicle detection, one counting line, count-based
density, four alert types, single-page dashboard. Already built. **Not extended.**

*Exit criterion:* a live demo on a laptop. Met.

### Phase 2 — MVP: the safety core

**Goal: a system that can be trusted with the charge track.** Nothing in this
phase is optional, and nothing outside it is built until it is done.

- Foundations: multi-camera `vision-worker` on RT-DETRv2/ONNX (ADR 0002, 0005);
  Redis event spine (ADR 0007); PostgreSQL/TimescaleDB; `core-api` with RBAC, JWT,
  audit; camera and zone CRUD with a polygon editor; WebRTC media gateway.
- **Calibration:** `CAM-012`, the site-survey homography workflow, and the
  operator calibration UI. *Everything below depends on this.*
- People: `PPL-001`…`PPL-007`, `PPL-020`.
- Horses: **the entire `HRS` P0 set** — `HRS-001`, `002`, `004`, `005`, `006`,
  `007`, `011`, `015`.
- Vehicles: `VEH-001`, `010`, `011`, `012`.
- Operations: `OPS-001`, `002`, `010`, `013`.
- Health: `CAM-001`…`004`, `CAM-011`, `CAM-012`; `SYS-002`, `007`, `011`.
- Alerts: `ALR-01`…`ALR-05`, `ALR-07`, `ALR-08`, `ALR-19`, `ALR-31`…`ALR-36`.
- Contextual arming (§4.3) and programme ingestion.
- KPIs: `KPI-01`…`03`, `13`, `14`, `15`, `16`.

*Exit criteria:* the latency budget in §15.4 is met at p99 on the real hardware;
`HRS-007` correctly degrades to `unknown` on every simulated camera failure;
`KPI-14` false-positive rates are measured on real footage and are within budget
for every P0 rule; the observability-coverage map (`SYS-011`) is honest.

**Phase 2 is the deployable event system.** Everything after it is improvement.

### Phase 3 — Production: the analytics platform

**Goal: a system that explains the crowd, not just counts it.**

- Flow analytics: `PPL-008`…`PPL-012`, `PPL-015`…`PPL-019`, `PPL-022`.
- **Crowd crush risk** (`SID-006`, `ALR-06`) — the highest-value item in this
  phase, and the one requiring the most validation.
- Security Incident Detection: the full `SID` module and `SID-011` fusion.
- Density-map regression model for crowds beyond detection's ceiling (`PPL-007`
  future work) — **the single most important accuracy investment in the roadmap.**
- Fire and smoke (`ALR-29`, `ALR-30`) with contextual arming. First custom model.
- Abandoned object (`ALR-21`), zone-gated.
- Remaining `VEH`, `OPS`, `CAM`, `SYS` features.
- Full KPI set; reporting and export; heatmaps.
- Site-specific horse validation set and, if the evidence demands it, a
  custom-trained horse model (§17, R-02).
- Hardening: HA event bus, worker failover, TensorRT, penetration test.

*Exit criteria:* crush-risk thresholds validated against recorded footage; `SID`
false-positive rate within budget; a full post-event report generated
automatically.

### Phase 4 — Enterprise

**Goal: a product, not a deployment.**

- Multi-venue, multi-tenant; venue templates; federated command centres.
- `HRS-005` formation-quality analytics and `HRS-018` — the commercial
  differentiator for equestrian events.
- Hardware interlock for `HRS-006` (track-side warning light), under a formal
  safety case.
- Operator-feedback learning loop for `SID-011` fusion weights.
- Predictive analytics: time-to-capacity, projected bottleneck formation,
  pre-emptive steward positioning.
- Custom-dataset track: tents, stalls, barriers, horse trailers (`VEH-002`,
  `HRS-014`).
- Emergency-vehicle recognition (`VEH-014`) — *only if* the dispatch integration
  of `OPS-013` proves insufficient. It probably will not.
- Edge inference at camera poles; offline-tolerant operation.
- SOC 2 / ISO 27001 posture; formal DPIA; independent security accreditation.

---

## 17. RISK REGISTER

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **R-01** | **Cameras cannot be surveyed and calibrated before the event** (assumption A3) | Medium | **Severe** — all crush-risk alerting is undefendable; density becomes incomparable | Confirm A3 immediately. Fallback: single-plane approximate calibration from known landmark distances, clearly flagged as low-accuracy. **Never silently fall back to counts.** |
| **R-02** | COCO `horse` recall collapses on a charging sorba (dust, blur, occlusion, dusk) | **High** | Severe — `HRS-004`/`006` are P0 | Capture a site-specific validation set at the earliest opportunity. Budget for a custom-trained horse model in Phase 3. Do not trust benchmark numbers. |
| **R-03** | Crush-risk thresholds (`PPL-012`, `SID-006`) ship unvalidated | Medium | **Severe** — false negatives kill; false positives destroy trust | Ship as *advisory, non-alarming* until validated against real footage. §15.1 rule 3 is binding. |
| **R-04** | Alert fatigue from an over-eager rule set | **High** | High — operators dismiss the alert that mattered | `KPI-14` from day one; storm suppression (§15.2); automatic demotion of noisy rules; conservative default arming. |
| **R-05** | Detection degrades at night and the dashboard renders it as "crowd went home" | **High** | High | `CAM-011` confidence health; occupancy confidence intervals; explicit degradation (§15.5). |
| **R-06** | Baroud smoke triggers continuous fire alarms | **Certain** if unmitigated | High | Contextual arming (§4.3). Already designed. |
| **R-07** | No machine-readable event programme (assumption A2) | Medium | Medium | Manual operator arming UI as a first-class fallback, designed in Phase 2, not bolted on. |
| **R-08** | GPU thermal throttling in an outdoor command tent | Medium | High | `SYS-002` throttle detection; predictive load-shed that never sheds track cameras. |
| **R-09** | Zone capacities and LOS thresholds never signed off (assumption A4) | Medium | High | Escalate to the event safety officer now. Placeholders must be visibly marked as unapproved in the UI until signed off. |
| **R-10** | Scope pressure to add face recognition or plate reading "just for the police" | Medium | **Existential** | ADR 0004 is architectural, not advisory. There is no component that could carry the data. The refusal is the product. |

---

## 18. VERIFICATION

Every feature in this document is verified by one of the following, and the
verification method is part of its definition of done:

- **Unit / property test** — geometry, rules, state machines. Line-crossing,
  polygon containment, and the `HRS-005` state machine are property-tested against
  generated tracks.
- **Recorded-footage regression suite** — a corpus captured at this venue, with
  ground-truth counts and annotated incidents. Every detection and analytics
  feature has a scored entry. **This corpus is the single most valuable engineering
  asset the project will build**, and its collection must begin before Phase 2
  development, not after.
- **Fault-injection test** — camera death, decode corruption, GPU throttle, bus
  lag, database loss. Verifies §15.5: every failure produces explicit degradation,
  never a plausible-looking number.
- **Latency test** — §15.4, measured at p99 on production hardware.
- **Operator acceptance** — an experienced steward or safety officer confirms the
  feature answers the question they actually ask.

A feature without a recorded-footage regression entry is not done, regardless of
whether it works on a developer's laptop.

---

## 19. OPEN QUESTIONS FOR THE CLIENT

Ordered by how much they change the build. The first three are blocking.

1. **Can cameras be physically surveyed for ground-plane calibration before the
   event?** (A3, R-01) — determines whether crush-risk alerting exists at all.
2. **Who signs off zone capacities and density thresholds?** (A4, R-09) — the
   event safety officer must own these numbers; engineering must not invent them.
3. **Will a machine-readable event programme be available each day?** (A2, R-07) —
   determines whether contextual arming is automatic or operator-driven.
4. Is the charge track / sorba model in §2.1 operationally correct, and is the
   terminology right for the operator UI?
5. What is the expected peak attendance, and what is the licensed venue capacity?
6. Are camera positions fixed, or will cameras move during the event? (Moving
   cameras invalidate calibration — `CAM-008`/`CAM-012`.)
7. What is the on-site network and power provision at each camera position? (A5 —
   determines central vs edge inference.)
8. Which authority receives `emergency`-severity alerts, and through what channel?
9. What is the required retention period for alert snapshots, and who may view
   them? (Default 30 days, access audited.)
10. Is there an existing dispatch or radio system to integrate with, for
    `OPS-013` and `HRS-017`?

---

*End of specification. Reviewed against ADR 0001–0007; no architectural decision
in this document supersedes an existing ADR. Where this specification implies a
new architectural decision — notably ground-plane calibration as a precondition
(§4.1), contextual arming (§4.3), and the `SID` module replacing behavioural
classification (§9) — those decisions are to be promoted to ADRs 0008, 0009, and
0010 respectively before Phase 2 implementation begins.*
