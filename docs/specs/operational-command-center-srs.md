# MANSOUR Vision — Operational Command Center Specification

**Software Requirements Specification (SRS) · Volume II**

| | |
|---|---|
| **Document** | Operational Command Center Specification |
| **Version** | 1.0 |
| **Status** | For review — senior engineering, government stakeholders, project management |
| **Date** | 2026-07-09 |
| **Owner** | Technical Director, Tomorrow Systems |
| **Baseline** | ADR 0001–0007 (`docs/adr/`) and the Detection & Analytics SRS (`docs/specs/detection-analytics-srs.md`, approved). Neither is revisited or modified by this document. |
| **Scope** | Every operational capability **outside** the AI engine. |

---

## 1. Purpose

Volume I specified what the platform **observes**. This volume specifies what the
platform **does about it** — and what the people in the command center do with it.

The AI engine is one module of perhaps twenty. It produces observations. An
observation that nobody sees, cannot verify, cannot act on, cannot hand over at
shift change, and cannot produce as evidence six months later at an inquest, has
no operational value whatsoever. **The engineering effort in this volume exceeds
that of Volume I, and it is where the platform succeeds or fails as a product.**

This document contains no code, no API definitions, and no database schema.

### 1.1 Who this system is for

Five distinct classes of user, with different authority, different legal
obligations, and different rights over the same data:

| Actor | Cares about | Legal position |
|---|---|---|
| **Event Operations** | Throughput, queues, capacity, staffing, commerce | Contractual duty to the organizer |
| **Police / Gendarmerie** | Public order, restricted areas, incident response | Statutory powers; evidentiary needs |
| **Civil Protection / Fire** | Evacuation routes, fire, structural risk, crowd crush | Statutory duty; incident command authority |
| **Emergency Medical** | Casualties, access routes, triage load | Duty of care; patient confidentiality |
| **Government decision makers** | Venue-wide situation, capacity compliance, escalation | Political and legal accountability |

**These are not five roles in one organisation. They are five organisations.**
That single fact drives §4 (multi-agency model) and is the most commonly botched
requirement in command-center software.

---

## 2. Design principles

Seven principles. Every requirement in this document derives from one of them, and
where a requested feature conflicts with one, the principle wins.

### 2.1 An alert is a machine observation. An incident is a human commitment.

The most important distinction in this volume, and the one most often collapsed.

An **alert** is what the AI engine, or a health check, emitted. It is cheap,
automatic, possibly wrong, and there may be forty of them per minute. Nobody owns
an alert.

An **incident** is a unit of work that a named human being has accepted
responsibility for. It has a lifecycle, an owner, a timeline, an audit trail, and
an outcome. Incidents are expensive and comparatively rare.

The relationships are many-to-many and both directions matter:

- **Many alerts → one incident.** A blocked gate produces `blocked entrance`,
  `queue too long`, `bottleneck`, `high density`, and `counterflow`. Five alerts.
  **One problem. One incident.**
- **An incident with no alert.** A steward radios in a fight. A visitor reports a
  lost child. The system saw nothing. **The incident is no less real**, and a
  platform that cannot represent it is a toy.
- **An alert with no incident.** The overwhelming majority. Dismissed, or
  auto-resolved when the condition clears. This is normal and healthy.

Software that treats "acknowledge the alert" as the terminal state has confused
noticing with responding.

### 2.2 The command center must degrade, not fail

The event proceeds whether or not the software is up. Every capability is
specified with an explicit answer to *"what happens when this is unavailable?"*

Concretely: if the network partitions, if the database is down, if the browser
crashes, if the operator's workstation dies, if the GPU melts — **the event's
safety must not depend on any of it.** The platform is an instrument that improves
decisions, never a control system the event cannot run without.

Corollary: **a critical alert that was displayed on a screen nobody was looking
at has not been delivered.** Delivery requires acknowledgement (§17).

### 2.3 The system never acts autonomously on the physical world

The platform recommends, alerts, and informs. It does not open gates, stop runs,
sound sirens, or dispatch. Every physical consequence passes through a human with
the authority to cause it, and that decision is recorded with their name on it.

The single contemplated exception — the `HRS-006` track-side hardware interlock —
is Phase 4, requires a formal safety case, and is out of scope here.

### 2.4 Evidence, not video

Any recorded frame may become evidence in a coroner's inquest, a criminal
prosecution, or a civil claim. From the moment of capture it must be treated as
such: integrity-sealed, chain-of-custody tracked, access-audited, and exportable
in a form that survives challenge by opposing counsel.

Designing a video player and adding evidence controls later does not work. §13 is
specified as an evidence system that happens to have a scrub bar.

### 2.5 Configuration is versioned, immutable, and attributable

Six months after the event, someone will ask: *"what was the density threshold for
the north gate at 21:47, who set it, and when?"* If the answer is "whatever is in
the settings table now," the platform cannot support an inquest.

Every configuration change is a new immutable version, attributed and timestamped.
Every incident and every alert records the **configuration version under which it
was raised** (§16).

### 2.6 Operators are a finite, fatiguing resource

The human factors literature is consistent that sustained active monitoring of
more than a handful of video feeds produces a sharp collapse in detection rate,
within tens of minutes. A 4×4 video wall staffed by one operator is decoration.

The platform therefore manages **operator workload and span of control as
first-class, monitored quantities** (§9), and its primary job is to *reduce* what
a human must watch — to direct attention, not to supply more of it.

### 2.7 Say what you do not know

Restated from Volume I §15.5, because it governs this volume too. Every displayed
value carries provenance. The prohibited failure mode is a number that looks
authoritative and means nothing. A camera that is down makes its zone `unknown`,
never `clear`.

---

## 3. Reading the catalogue

Same discipline as Volume I. Each feature carries a stable ID (`MOD-NNN`),
a **description**, a **business value**, a **priority** (`P0` cannot ship without ·
`P1` core · `P2` valuable · `P3` future), a **complexity** (`S` days · `M` 1–2
weeks · `L` 3–6 weeks · `XL` a quarter or blocked on an external dependency), the
**primary actor**, and **future improvements**.

Module prefixes: `CMG` camera management · `ZON` zones · `INC` incidents ·
`ALM` alerts · `OPR` operators · `RBA` roles and access · `EVT` events ·
`RPT` reporting · `RPL` replay and evidence · `GIS` mapping · `CAL` calibration ·
`CFG` configuration · `NTF` notifications · `AUD` audit · `ADM` administration ·
`HLT` health · `DSH` dashboard · `PSO` public safety operations ·
`HAO` horse arena operations · `PKO` parking operations.

Volume I identifiers (`PPL`, `VEH`, `HRS`, `OPS`, `SID`, `ALR`, `CAM`, `SYS`,
`KPI`) are referenced but never redefined.

---

## 4. The multi-agency model

Police, Civil Protection, medical, and event operations share one venue, one set
of cameras, and one situation — but they do not share one chain of command, one
legal authority, or one right of access to the same records. A single flat RBAC
model over a single flat data set cannot express this, and pretending otherwise
is how such systems fail their first accreditation.

### 4.1 Common operating picture, private working space

The platform maintains a **Common Operating Picture (COP)**: the shared,
authoritative view of the venue — zone occupancy, density, camera health, active
critical incidents, route status. Every agency sees the same COP. Divergent
pictures are how agencies kill each other's people.

Around the COP, each agency has a **private working space**: its own incident
notes, its own internal tasking, its own dispositions. A medical note on a
casualty is not visible to event commerce staff. A police tactical annotation is
not visible to the organizer.

**Promotion from private to COP is an explicit, attributed act.** An agency
commander decides that something the rest of the venue must know is now shared.

### 4.2 Authority is scoped four ways, not one

Access is evaluated over four axes simultaneously — role, agency, zone, and time —
rather than by role alone:

- **Role** — what kind of action (view, acknowledge, resolve, configure, export).
- **Agency** — whose data, and whose incidents.
- **Zone** — which part of the venue. A gate steward supervisor has no business
  in the medical tent's feeds.
- **Time** — active shift, active event. Credentials issued for one event do not
  carry to the next.

### 4.3 Incident command transfer

A critical incident may be **transferred** between agencies — an event-operations
crowd incident becomes a Civil Protection incident becomes a police incident. The
transfer is explicit, requires acceptance by the receiving agency, is timestamped,
and **the full incident history transfers with it.** History is never rewritten
and never truncated on transfer.

### 4.4 Break-glass access

Emergencies do not respect access-control matrices. A designated senior role may
invoke **break-glass**: temporary elevation beyond normal scope, which is granted
immediately (never blocked pending approval), and which raises a high-visibility
audit event, notifies the security officer, is time-boxed, and requires written
justification within a bounded window.

**Break-glass that is difficult to invoke gets circumvented by password sharing,
which is worse.** Make it easy, make it loud, make it reviewed.

---

## 5. Module 1 — Camera Management (`CMG`)

### CMG-001 — Camera registration
**Description.** Add a camera by protocol (`RTSP`, `ONVIF`, `USB`, `file`),
capture its identity, name, model, firmware, location, and zone assignment.
Credentials are captured into the secret store and **never stored, displayed, or
logged in plaintext** — the record holds a secret reference, not a password.
**Business value.** Onboarding a hundred cameras must take an afternoon, not a
week. RTSP URLs with embedded credentials are the most commonly leaked value in
any CCTV deployment.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Bulk import from an NVR inventory or a spreadsheet.

### CMG-002 — ONVIF discovery and profile negotiation
**Description.** Discover ONVIF-conformant devices on the local network; read
capabilities (profiles, resolutions, codecs, PTZ support, temperature); negotiate
the analytic and the recording stream separately.
**Business value.** Removes manual URL construction, the largest source of
onboarding error. Negotiating a low-resolution analytic substream alongside a
high-resolution recording stream is what makes per-GPU camera capacity achievable
(ADR 0005).
**Priority** P1 · **Complexity** L · **Actor** Administrator
**Future.** ONVIF Profile G/T recording control; vendor-quirk compatibility matrix.

### CMG-003 — Camera lifecycle states
**Description.** An explicit state machine: `registered → configured →
calibrated → commissioned → live → maintenance → decommissioned`. A camera cannot
reach `commissioned` without a valid calibration (`CAL-002`) and a zone assignment.
**Business value.** Prevents the failure that matters: a camera that appears on
the wall, looks like it is working, and is silently excluded from every safety
computation because it was never calibrated. The state machine makes that
impossible rather than merely unlikely.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Commissioning checklist with sign-off, exportable as a handover
document.

### CMG-004 — Camera groups
**Description.** Arbitrary, overlapping groupings — by zone, by agency, by
purpose (`track cameras`, `perimeter`, `parking`), by physical infrastructure
(`pole 14`, `switch B`). Groups drive video-wall layouts, permissions, bulk
operations, and correlated-failure diagnosis.
**Business value.** When eight cameras drop simultaneously, the group they share
(`switch B`) tells the technician it is a network fault, not eight camera faults.
**Priority** P1 · **Complexity** S · **Actor** Administrator
**Future.** Automatic group inference from failure correlation.

### CMG-005 — PTZ control and presets
**Description.** Pan/tilt/zoom control with named presets, preset tours, and a
priority-based lock so two operators cannot fight over one camera. **A PTZ camera
that has moved off its calibrated preset is uncalibrated** and must declare itself
so (`CAL-005`).
**Business value.** Verification of an alert frequently requires a closer look.
The calibration coupling is essential and easily missed: a PTZ camera silently
invalidates every ground-plane metric the moment someone nudges it.
**Priority** P1 · **Complexity** L · **Actor** Operator
**Future.** Auto-slew to the coordinate of a `SID-011` incident (Volume I) — the
operator's most-wanted feature, and the one most likely to be abused. It must be
operator-initiated, never automatic.

### CMG-006 — Virtual line management
**Description.** Draw, name, and configure counting lines on a live frame.
Explicit inward-side declaration. Multiple lines per camera. Bound to a zone.
Changes are versioned (§16) and propagate to the vision worker within seconds.
**Business value.** The counting geometry is the foundation of every occupancy and
flow metric. It must be adjustable by an operations supervisor, on site, without
an engineer.
**Priority** P0 · **Complexity** M · **Actor** Supervisor
**Future.** Line-placement quality advisor — warn when a line is drawn parallel to
the observed direction of travel, which is the single most common configuration
error and silently produces near-zero counts.

### CMG-007 — Zone polygon editor
**Description.** Draw zone polygons on a live frame; simultaneously visualize them
projected onto the venue map via the camera's homography, so the operator sees
where the polygon *actually* lands on the ground.
**Business value.** Per ADR 0003, every static feature is a polygon, and polygon
accuracy is now the dominant determinant of alert quality. The dual image/map view
is what makes an operator's polygon correct rather than plausible.
**Priority** P0 · **Complexity** L · **Actor** Supervisor
**Future.** Suggest polygon boundaries from detected ground-plane structure.

### CMG-008 — Camera health surface
**Description.** Surfacing of the Volume I `CAM-001`…`CAM-013` health signals per
camera: online state, latency, analytic FPS, bitrate, decode errors, tampering,
detection-confidence trend, calibration validity, assigned worker.
**Business value.** The health of the instrument gates the credibility of every
measurement it produces.
**Priority** P0 · **Complexity** M · **Actor** Operator, Administrator
**Future.** Per-camera health history and MTBF ranking, driving the maintenance
schedule.

### CMG-009 — Maintenance mode and work orders
**Description.** Take a camera out of service explicitly. Suppresses its alerts,
excludes it from the COP and from `SYS-011` coverage, records who, why, expected
duration. Generates a work order with a location, a fault class, and a photograph.
**Business value.** Prevents alert storms during scheduled work. Critically, a
camera in maintenance **degrades venue coverage honestly** rather than pretending
its zone is fine.
**Priority** P1 · **Complexity** S · **Actor** Administrator, Technician
**Future.** Mobile technician app; automatic work-order creation from a sustained
health fault.

### CMG-010 — Firmware and configuration inventory
**Description.** Record firmware version, last update, configuration checksum, and
known-vulnerability status per device model.
**Business value.** IP cameras are the softest attack surface on any venue
network, and an unpatched fleet is a finding at every security accreditation.
**Priority** P2 · **Complexity** M · **Actor** Administrator, Security Officer
**Future.** Firmware update orchestration with staged rollout. **Never automatic
during an event.**

### CMG-011 — Snapshot capture and retention
**Description.** On-demand and alert-attached snapshots. Retention per the policy
in the data model (default 30 days), subject to legal hold (`RPL-009`). **Every
snapshot access is an audited event** (`AUD-004`).
**Business value.** The only imagery of people the platform retains by default,
and therefore the only place a privacy reviewer will look hard.
**Priority** P0 · **Complexity** S · **Actor** Operator
**Future.** Automatic redaction of incidental faces on export. Note that this
*blurs* faces; it does not recognize them, and does not violate ADR 0004.

### CMG-012 — Camera assignment to workers
**Description.** View and override the scheduler's assignment of cameras to
inference workers. Priority classes: **track cameras are never load-shed**
(Volume I §15.4).
**Business value.** The capacity picture and the safety guarantee meet here.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Automatic rebalancing on worker loss, track cameras re-homed first.

### CMG-013 — Camera coverage and blind-spot registration
**Description.** Per camera: GPS position, bearing, field of view, mounting
height, and the resulting **ground coverage polygon** — computed from the
calibration homography, not from the lens specification.
**Business value.** Feeds the blind-spot map (`GIS-005`). A coverage polygon
derived from the lens datasheet is a fiction: it ignores every wall, tent, and
stand between the camera and the ground.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Occlusion-aware viewshed from a venue terrain and structure model.

---

## 6. Module 2 — Zone Management (`ZON`)

### ZON-001 — Zone definition
**Description.** Create a semantic, venue-level zone: name, `kind` (per ADR 0003),
GPS boundary, floor area in m², maximum occupancy, risk level, owning agency.
Distinct from the per-camera polygon (`CMG-007`), which is its geometric
observation.
**Business value.** The zone is the unit in which every operational conversation
happens. "The north gate is at capacity," never "camera 14 sees 200 people."
**Priority** P0 · **Complexity** M · **Actor** Supervisor
**Future.** Zone templates per venue archetype.

### ZON-002 — Zone capacity and threshold configuration
**Description.** Per-zone maximum occupancy and per-zone LOS density bands.
**Values are signed off by the event safety officer, not by engineering.** Until
signed off, thresholds are visibly marked *unapproved* in every view that uses
them, and the zone cannot raise crush-risk alerts.
**Business value.** Volume I risk R-09. Engineering must not invent the number at
which a crowd becomes dangerous; a named, accountable person must own it.
**Priority** P0 · **Complexity** S · **Actor** Safety Officer
**Future.** Capacity derivation from measured floor area and the agreed LOS band,
proposed to the safety officer for approval rather than assumed.

### ZON-003 — Multi-camera zone coverage
**Description.** Bind many cameras to one zone. Occupancy is de-duplicated across
overlapping coverage **by ground-plane geometry, never by appearance matching**
(ADR 0004, ADR 0006). Show, per zone, which fraction of its area is observed by at
least one healthy calibrated camera.
**Business value.** The difference between "we have a camera on the zone" and "we
can see the zone."
**Priority** P0 · **Complexity** L · **Actor** Administrator
**Future.** Coverage-gap-driven camera placement recommendations.

### ZON-004 — Zone hierarchy
**Description.** Zones nest: `Venue → Sector → Zone → Sub-zone`. Occupancy and
alerts roll up. A parent's occupancy is not the naive sum of its children's, and
the platform must not pretend it is where coverage overlaps.
**Business value.** Government stakeholders ask about the venue; a gate supervisor
asks about lane 3. One data model, two questions.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Cross-sector flow matrices.

### ZON-005 — Zone risk level and escalation profile
**Description.** Each zone carries a risk level that modulates alert severity,
notification routing, and required operator coverage. A `warning` in the charge
track is a `critical` anywhere else.
**Business value.** One rule set, correctly weighted by where it fires. Prevents
both under-reaction on the track and alarm fatigue in the car park.
**Priority** P1 · **Complexity** M · **Actor** Safety Officer
**Future.** Dynamic risk level driven by the programme — the track's risk rises
when a sorba stages.

### ZON-006 — Zone state and manual override
**Description.** Operator-settable zone states — `open`, `closed`, `holding`,
`evacuating`, `restricted` — which take precedence over inferred state, are
attributed and timestamped, and drive alert arming.
**Business value.** Principle 2.3. The system observes; the commander decides. A
zone the commander has closed must not keep alerting that it is empty.
**Priority** P0 · **Complexity** M · **Actor** Supervisor, Incident Commander
**Future.** Zone-state change propagation to visitor-facing signage.

### ZON-007 — Zone occupancy reconciliation controls
**Description.** Operator visibility of, and control over, the reconciliation
machinery of ADR 0006: current occupancy, its confidence, the age of its last
anchor, and a **manual zero-reset** for a zone confirmed empty by eye.
**Business value.** The end-of-day residual (`KPI-17`) is how the platform proves
its own accuracy. The manual reset is how a human corrects an instrument that has
drifted. Both are trust-building, and neither exists in competing products.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Guided reconciliation walkthrough at venue open and close.

### ZON-008 — Zone-to-agency assignment
**Description.** Each zone has an owning agency and a set of agencies with
visibility. Drives incident routing (§4.2) and default notification targets.
**Business value.** An incident in the medical tent routes to medical command, not
to the commerce team.
**Priority** P1 · **Complexity** S · **Actor** Administrator
**Future.** Time-varying ownership across event phases.

---

## 7. Module 3 — Incident Management (`INC`)

> Per principle 2.1, this is the module in which the platform stops being an
> observation tool and becomes an operational one.

### INC-001 — Incident lifecycle
**Description.** An explicit, auditable state machine:

```
  created ──▶ assigned ──▶ acknowledged ──▶ investigating ──┬──▶ resolved ──▶ closed
     │            │              │                │          │
     └────────────┴──────────────┴────────────────┴──▶ escalated ──▶ (re-assigned)
                                                             │
                                                        cancelled  (false positive)
```

Every transition records actor, timestamp, and reason. **No transition is
automatic except `created`.** `resolved` means the condition has ended;
`closed` means the record is complete, reviewed, and no further work is expected —
a supervisor act, not an operator act. `cancelled` exists so that false positives
are recorded as such and feed `KPI-14`, rather than being silently deleted.

**Business value.** The state machine *is* the accountability. At any instant,
every open incident has exactly one named owner, and the record of who knew what,
when, survives the event.
**Priority** P0 · **Complexity** L · **Actor** Operator, Supervisor
**Future.** Configurable per-agency lifecycles — police and medical do not close
incidents on the same criteria.

### INC-002 — Incident record
**Description.** Every incident carries: unique ID (human-speakable — `INC-0417`,
not a UUID, because it will be read aloud over a radio), priority, severity,
category, sub-category, current owner, owning agency, location (ground
coordinate), zone, contributing cameras, contributing alerts, full timeline,
comments, attachments, snapshots, video segments, **and the configuration version
in force when it was raised** (§16, principle 2.5).
**Business value.** This record is what exists six months later. Everything else
is transient.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Structured casualty and damage fields for statutory reporting.

### INC-003 — Incident creation from alerts (correlation)
**Description.** Alerts are correlated into candidate incidents by zone, time
window, and causal rule grouping (Volume I §15.2). The operator confirms, merges,
or splits. **Correlation proposes; a human disposes.**
**Business value.** Five alerts, one problem, one incident. Without this the
operator is doing the correlation in their head, at 3am, under load, and getting
it wrong.
**Priority** P0 · **Complexity** L · **Actor** Operator
**Future.** Learned correlation weights from operator merge/split behaviour.

### INC-004 — Manual incident creation
**Description.** Create an incident with no originating alert — from a radio call,
a steward report, a visitor complaint, an observation out of the window.
**Business value.** Principle 2.1. **Most real incidents at a real event will
originate here, not from the AI.** A platform that cannot represent them will be
abandoned by its operators within a day, and everything it does capture will be a
biased sample of only what the cameras happened to catch.
**Priority** P0 · **Complexity** S · **Actor** Operator
**Future.** Mobile steward app; public reporting channel with triage.

### INC-005 — Incident assignment and ownership
**Description.** Assign to an operator, a role, or an agency. Explicit acceptance
transitions to `acknowledged`. Unacknowledged assignment escalates on a timer
(`NTF-005`). Ownership is singular and always populated.
**Business value.** Diffusion of responsibility is the classic command-center
failure. Exactly one person owns each incident, always.
**Priority** P0 · **Complexity** M · **Actor** Supervisor
**Future.** Load-aware assignment suggestions from `OPR-004` workload.

### INC-006 — Incident escalation
**Description.** Escalate by severity, by chain of command, or by agency transfer
(§4.3). Escalation is explicit, attributed, and requires acceptance. Automatic
escalation on unacknowledged timers raises the notification, **never silently
reassigns ownership.**
**Business value.** An escalation that transfers the alert but not the ownership
creates the illusion of a response. The receiving agency must accept.
**Priority** P0 · **Complexity** M · **Actor** Supervisor, Commander
**Future.** Escalation matrices per event and per incident category.

### INC-007 — Incident timeline
**Description.** An immutable, append-only chronology: state transitions,
comments, attachments, alerts joined, video bookmarked, notifications sent and
their delivery receipts, break-glass events. Rendered as the incident's narrative.
**Business value.** This is the artifact that goes to the inquest. It must be
complete, ordered, attributed, and impossible to retrospectively tidy up.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Automatic narrative summary for the post-event report — drafted by the
system, **always edited and signed by a human before it leaves the building**.

### INC-008 — Comments, attachments, and evidence linkage
**Description.** Free-text comments (attributed, timestamped, never editable —
corrections are appended, not applied). Attachments. Links to snapshots and to
sealed video segments (`RPL-004`).
**Business value.** An editable comment history has no evidentiary value.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Voice-note capture and transcription for operators whose hands are on
a radio.

### INC-009 — Incident categories and taxonomy
**Description.** A controlled taxonomy: crowd safety, medical, fire, public order,
traffic, animal, infrastructure, security, lost person, system fault. Category
determines the default agency, notification routing, mandatory fields, and the
statutory report it feeds.
**Business value.** Free-text categories make post-event analysis impossible and
statutory reporting manual.
**Priority** P1 · **Complexity** S · **Actor** Administrator
**Future.** Alignment with the national civil-protection incident taxonomy — to be
obtained from the client (§29).

### INC-010 — Incident map and live view
**Description.** Open incidents on the GIS map (`GIS-004`), with severity, age,
owner, and one-click access to the contributing live feeds and to the sealed
pre-roll (`RPL-002`).
**Business value.** The single screen an incident commander looks at.
**Priority** P0 · **Complexity** M · **Actor** Commander
**Future.** Responder position overlay, given a personnel-tracking integration.

### INC-011 — Incident merge and split
**Description.** Merge duplicate incidents, preserving both timelines. Split an
incident that turned out to be two. Both operations are audited and reversible in
the record, never in the history.
**Business value.** Under load, duplicates are created. The alternative — deleting
one — destroys evidence.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Duplicate detection at creation time.

### INC-012 — After-action review
**Description.** Post-incident structured review: what was detected, when, by
what; time to acknowledge, to resolve; what the system missed; what the operator
saw that the system did not. Feeds `KPI-13`, `KPI-14`, and rule tuning.
**Business value.** **The only mechanism by which the platform improves.** An
incident the AI missed is the most valuable single data point the project can
obtain, and it is worthless if nobody records that it was missed.
**Priority** P1 · **Complexity** M · **Actor** Supervisor, Safety Officer
**Future.** Automatic identification of near-miss incidents from the detection
record.

### INC-013 — Legal hold on incident evidence
**Description.** Flag an incident such that all associated snapshots, video
segments, alerts, and configuration versions are **exempted from automatic
retention deletion** until the hold is lifted by an authorized role. Lifting is
audited and requires a reason.
**Business value.** Automatic 30-day snapshot deletion is correct policy and would
destroy the evidence of a fatality four weeks before anyone requests it. This
feature is the reconciliation of a privacy obligation with a legal one, and it
must exist before the first event, not after the first inquest.
**Priority** P0 · **Complexity** M · **Actor** Legal, Security Officer
**Future.** Automatic proposed hold on any incident with a casualty field
populated.

---

## 8. Module 4 — Alert Management (`ALM`)

### ALM-001 — Alert queue and triage
**Description.** A prioritized, filterable working queue: by severity, zone,
agency, camera, rule, age, and acknowledgement state. Default sort is not
chronological — it is **by decayed severity**, so a 10-minute-old critical
outranks a fresh warning.
**Business value.** The operator's primary work surface. Chronological alert lists
are how critical alerts get buried by warnings.
**Priority** P0 · **Complexity** M · **Actor** Operator
**Future.** Per-operator queue views bound to assigned zones (`OPR-003`).

### ALM-002 — Alert acknowledgement and disposition
**Description.** Acknowledge, dismiss with a **mandatory one-click reason code**,
promote to incident, or link to an existing incident. Dismissal reasons are a
controlled list feeding `KPI-14`.
**Business value.** Volume I §15.1 makes the measured false-positive rate binding
on us. It is only measurable if every dismissal is reasoned. A dismiss button
without a reason code destroys the platform's only self-correction mechanism.
**Priority** P0 · **Complexity** S · **Actor** Operator
**Future.** Reason-code trends surfaced automatically to the rule owner.

### ALM-003 — Alert clustering and storm suppression surface
**Description.** Operator-facing rendering of the clustering in Volume I §15.2: a
parent alert with contributing children, expandable. When suppression engages the
platform announces it (`ALR-42`) and shows what was suppressed. **`emergency`
severity is never suppressed.**
**Business value.** One problem presents as one row. The operator can still see
all five underlying alerts, which is what maintains trust in the clustering.
**Priority** P1 · **Complexity** L · **Actor** Operator
**Future.** Root-cause ranking within a cluster.

### ALM-004 — Rule arming and suppression control
**Description.** View and control the contextual arming state of every rule
(Volume I §4.3): what is armed, what is disarmed, why, by what schedule, and until
when. One-click manual re-arm. **A disarmed rule is always visible.**
**Business value.** A system that silently disables its own alarms is not a safety
system. This screen is the first thing an auditor will ask to see.
**Priority** P0 · **Complexity** M · **Actor** Supervisor
**Future.** Simulation of an arming schedule against yesterday's alert stream,
before committing it.

### ALM-005 — Manual alert suppression (with expiry)
**Description.** Temporarily suppress a specific rule on a specific camera or
zone — the known-faulty camera, the stall being erected in a restricted area.
**Suppression always has a mandatory expiry, a reason, and an owner**, is audited,
and is shown on the COP. It cannot be applied to `emergency` severity.
**Business value.** Operators will otherwise ignore the alert channel, which is
untraceable suppression with no expiry.
**Priority** P0 · **Complexity** S · **Actor** Supervisor
**Future.** Expiring-suppression digest at shift handover (`OPR-006`).

### ALM-006 — Rule threshold management
**Description.** View and edit rule thresholds per zone, per event. Every change
is a new configuration version (§16), attributed. Thresholds requiring safety-
officer sign-off (`ZON-002`) cannot be changed by an operator at all.
**Business value.** Separates the parameters an operator may tune (queue-length
warning) from those they may not (crush-risk density).
**Priority** P1 · **Complexity** M · **Actor** Supervisor, Safety Officer
**Future.** Threshold recommendation from the recorded-footage regression corpus.

### ALM-007 — Alert-to-evidence linkage
**Description.** Every alert carries its snapshot and a pointer to the sealed video
segment spanning its pre-roll and duration (`RPL-002`).
**Business value.** Verification in one click. An operator who must hunt for the
footage will dismiss the alert instead.
**Priority** P0 · **Complexity** M · **Actor** Operator
**Future.** Side-by-side comparison against the last confirmed true positive of
the same rule.

### ALM-008 — Rule performance dashboard
**Description.** Per rule, per zone: fire rate, confirm rate, dismiss rate by
reason, mean time to acknowledge. Rules exceeding their false-positive budget are
flagged and **automatically demoted in severity** (Volume I §15.1 rule 4).
**Business value.** The platform polices its own noise. This screen is aimed at
the engineering team, and it is P0 because alarm fatigue is risk R-04.
**Priority** P0 · **Complexity** M · **Actor** Engineering, Safety Officer
**Future.** Automatic proposed threshold adjustments with an offline backtest.

---

## 9. Module 5 — Operator Management (`OPR`)

### OPR-001 — Operator identity and competence
**Description.** Operator records, agency affiliation, certifications, authorized
zones, authorized actions, and competence expiry. An operator whose certification
has lapsed cannot be assigned incidents in the zones it covered.
**Business value.** Statutory in some jurisdictions; defensible everywhere.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Integration with the client's HR or training system.

### OPR-002 — Shift and roster management
**Description.** Shifts, rosters, on-duty state, break scheduling, and the current
staffing level against the event's required staffing profile.
**Business value.** An unstaffed console during a critical alert is the failure
mode principle 2.2 exists to prevent.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Fatigue-aware rostering.

### OPR-003 — Zone assignment and span of control
**Description.** Each on-duty operator is assigned a set of zones and cameras.
**The platform enforces a configurable maximum span of control** and warns when a
console is assigned more active feeds or more open incidents than the configured
limit.
**Business value.** Principle 2.6. Sustained active monitoring degrades sharply
beyond a handful of feeds. A 4×4 video wall with one operator is decoration, and
the platform should say so out loud rather than participate in the fiction.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Empirically derived span limits from this platform's own
`KPI-18` response-latency data, per zone risk level.

### OPR-004 — Operator workload and console health
**Description.** Live per-operator: open incidents owned, alerts pending
acknowledgement, mean response latency this shift, time since last interaction.
**Business value.** A console showing no interaction for twenty minutes is either
an idle zone or an absent, asleep, or incapacitated operator. Both need a
supervisor to look.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Attention-management: automatic rebalancing of alert routing away from
an overloaded console.

### OPR-005 — Unassigned-coverage alarm
**Description.** If any zone whose risk level is `critical` — the charge track,
the emergency routes — has **no on-duty operator assigned**, the platform raises a
system alert to the supervisor.
**Business value.** "Is anyone actually watching the track right now?" is the only
question that matters during a run, and until now no system has been able to
answer it.
**Priority** P0 · **Complexity** S · **Actor** Supervisor
**Future.** Coverage requirement varying with the programme state — the track
requires two assigned operators when a sorba is staged.

### OPR-006 — Shift handover
**Description.** A structured, signed handover: open incidents with their state,
active suppressions and their expiries, disarmed rules, cameras in maintenance,
degraded zones, outstanding actions, and the outgoing supervisor's narrative.
Requires an explicit acceptance signature from the incoming supervisor.
**Business value.** **The most under-built feature in every command-center product
on the market, and the point at which real incidents are lost.** A suppression set
at 14:00 with no expiry and no handover note is an invisible blind spot at 22:00.
**Priority** P0 · **Complexity** M · **Actor** Supervisor
**Future.** Automatic handover-pack generation, reviewed and signed rather than
composed.

### OPR-007 — Operator activity record
**Description.** Alerts acknowledged, incidents owned and resolved, response
latency distribution. Visible **only to supervisor and auditor roles.**
**Business value.** Operational readiness measurement. Volume I is explicit that
this is **not a staff-surveillance tool** and must not be presented as one. A
platform that refuses to profile visitors and then profiles its own staff has
learned nothing.
**Priority** P2 · **Complexity** S · **Actor** Supervisor
**Future.** Anonymized, aggregate benchmarking across shifts rather than
individuals.

---

## 10. Module 6 — User Roles and Access (`RBA`)

### RBA-001 — Role model
**Description.** Seeded roles: `viewer`, `operator`, `supervisor`, `incident
commander`, `safety officer`, `administrator`, `security officer`, `auditor`,
`technician`, `agency liaison`. Permissions are `resource:action` grants,
composable into custom roles.
**Business value.** Least privilege, expressed in the vocabulary of the customer's
own organisation chart.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Role templates per agency type.

### RBA-002 — Four-axis authorization
**Description.** Every access decision evaluates role **and** agency **and** zone
scope **and** temporal scope (active shift, active event), per §4.2.
**Business value.** Role alone cannot express "a gate supervisor, from the
gendarmerie, for the north sector, during this event only." Every real deployment
needs exactly that sentence.
**Priority** P0 · **Complexity** L · **Actor** Administrator
**Future.** Policy-as-code with a simulation harness — *"what can this user see?"*
answered before granting, not after a breach.

### RBA-003 — Separation of duties
**Description.** `auditor` may read the audit log and nothing else.
**`administrator` cannot delete or modify audit entries, cannot lift a legal hold,
and cannot grant themselves an auditor role.** Legal hold lifting requires two
distinct authorized users.
**Business value.** The difference between an audit log and a log is that an
attacker holding the highest application privilege still cannot erase their trail.
Accreditation reviewers test exactly this.
**Priority** P0 · **Complexity** M · **Actor** Security Officer
**Future.** Dual-authorization on further destructive actions.

### RBA-004 — Authentication
**Description.** Argon2id password hashing, mandatory MFA for `supervisor` and
above, account lockout on failed attempts, short-lived access tokens, refresh
tokens stored **hashed** so a database compromise yields no usable session.
**Business value.** Credential stuffing is not defeated by per-IP rate limiting.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** SSO / SAML / OIDC federation against the agency's directory —
**required** for any real government deployment, and to be scoped early.

### RBA-005 — Session management
**Description.** Concurrent-session limits, forced revocation, idle timeout tuned
per role, and **an explicit exemption for active console operators**, whose
sessions must not expire mid-incident.
**Business value.** A security control that logs the operator out during a crowd
crush is a safety hazard. This tension is real and must be resolved deliberately:
idle timeout applies to *inactivity*, and an operator watching a screen is not
idle. Presence detection, not keystroke detection.
**Priority** P1 · **Complexity** M · **Actor** Security Officer
**Future.** Console-bound sessions tied to a physical workstation.

### RBA-006 — Break-glass access
**Description.** Per §4.4: immediate temporary elevation, time-boxed, loudly
audited, notified to the security officer in real time, with mandatory written
justification within a bounded window. **Never blocked pending approval.**
**Business value.** Break-glass that is hard to invoke is circumvented by password
sharing, which is untraceable. Make it easy, loud, and reviewed.
**Priority** P1 · **Complexity** M · **Actor** Incident Commander
**Future.** Automatic post-hoc review workflow for every invocation.

### RBA-007 — Agency and tenancy administration
**Description.** Onboard an agency, define its zone visibility, its private
working space, and its COP promotion rights (§4.1).
**Priority** P1 · **Complexity** L · **Actor** Administrator
**Future.** Cross-venue federation of a single agency's identity.

---

## 11. Module 7 — Event Management (`EVT`)

> An **event** is not a row in a table. It is a versioned, immutable bundle of
> everything that defines how the platform behaves for a given occasion — and the
> ability to reproduce that bundle exactly, months later, is what makes an inquest
> survivable.

### EVT-001 — Event definition
**Description.** Create an event: name, type (`moussem`, `festival`, `concert`,
`sports`, `state visit`), venue, dates, operating hours, licensed capacity,
participating agencies, and the responsible safety officer.
**Business value.** The platform is a product, not a deployment. Multi-event
support is what makes the second sale cheaper than the first.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Event templates per type; clone-from-last-year.

### EVT-002 — Event configuration bundle
**Description.** An event owns its zones, thresholds, alert rules and their arming
schedules, camera assignments, virtual lines, polygons, operator rosters,
notification routing, and escalation matrices. Activating an event atomically
applies the whole bundle.
**Business value.** No hand-editing of forty settings between a football match and
a moussem. Also the unit of backup, review, and sign-off.
**Priority** P1 · **Complexity** L · **Actor** Administrator
**Future.** Bundle diffing between events and between years.

### EVT-003 — Event schedule and programme
**Description.** The event's programme as a first-class, machine-readable input:
gates open, tbourida runs, prayer times, performances, VIP movements, gates close.
Drives contextual arming (Volume I §4.3), baseline learning, and reporting periods.
Editable live, because programmes slip.
**Business value.** Volume I assumption A2 is load-bearing. Contextual arming —
without which the smoke detector alarms on every baroud volley — is driven from
here.
**Priority** P0 · **Complexity** M · **Actor** Supervisor, Organizer
**Future.** Ingestion from the organizer's scheduling system; automatic reconcil-
iation of the planned programme against the observed one (`HRS-011` detects a run
whether or not the schedule says so). **A run that happens off-schedule is itself
worth an alert.**

### EVT-004 — Event phases
**Description.** `setup → pre-open → open → peak → wind-down → egress → teardown`.
Each phase carries its own thresholds, arming, staffing requirement, and dashboard
layout.
**Business value.** During setup, vehicles in pedestrian zones are normal and
would otherwise alarm continuously. During egress, exit rules matter and entry
rules do not. One threshold set cannot serve both.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Automatic phase transition proposal from observed flow, confirmed by a
human.

### EVT-005 — Event activation and rollback
**Description.** Activate exactly one event per venue. Activation is a single
audited transaction. Rollback to the previous bundle is one action.
**Business value.** A misconfiguration discovered at 08:00 on the opening day must
be recoverable in seconds, not by editing forty screens.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Staged activation with a dry-run against yesterday's stream.

### EVT-006 — Event configuration sign-off
**Description.** Before an event may be activated, its safety-critical parameters
— zone capacities, LOS bands, escalation matrices, staffing profile — require
**explicit sign-off by the named safety officer.** Unapproved values are visibly
marked and block crush-risk alerting (`ZON-002`).
**Business value.** Volume I risk R-09, made structural. Engineering cannot ship a
number it invented for the density at which a crowd becomes dangerous.
**Priority** P0 · **Complexity** M · **Actor** Safety Officer
**Future.** Sign-off pack exported as a signed PDF for the event's safety file.

### EVT-007 — Multi-event and historical isolation
**Description.** Telemetry, incidents, and audit records are partitioned by event.
Credentials issued for one event do not carry to the next (§4.2 temporal scope).
Historical events remain queryable and are never mutated.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Year-over-year comparative analytics for the same moussem.

---

## 12. Module 8 — Reporting (`RPT`)

> A report is a **statement made by an organisation to an authority**. Its
> defining property is not that it renders a chart; it is that its numbers can be
> reproduced, its provenance stated, and its uncertainty disclosed.

### RPT-001 — Report engine and scheduling
**Description.** Parameterized report definitions, run on demand or on a schedule,
delivered by the notification channels of §17. Every generated report is immutable,
versioned, and records the configuration version and the data-completeness state
at generation time.
**Business value.** A report regenerated next month must produce the same numbers,
or it must explain why not.
**Priority** P1 · **Complexity** L · **Actor** Supervisor
**Future.** Self-service report builder for supervisors.

### RPT-002 — Data-completeness disclosure
**Description.** **Every report carries a mandatory provenance header**: what
fraction of the venue was observed by a healthy, calibrated camera over the
reporting period (`SYS-011`, `KPI-16`); which cameras were down and when; which
zones were uncalibrated; the occupancy reconciliation residual per gate (`KPI-17`).
**Business value.** Principle 2.7, applied to the artifact that leaves the
building. **A report that says "182,000 visitors" without saying "the east gate
camera was down for four hours" is a lie of omission**, and it is the lie that
destroys a vendor's credibility when it is discovered. This section is
non-removable and is not a footnote.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Confidence intervals on every headline figure, not just a coverage
statement.

### RPT-003 — Daily operational report
**Description.** Per operating day: visitors in/out by hour and gate, peak
occupancy and time, density-hours by zone, alerts by type and disposition,
incidents by category and outcome, camera uptime, staffing.
**Priority** P0 · **Complexity** M · **Actor** Event Operations
**Future.** Automatic distribution at venue close.

### RPT-004 — Weekly, monthly, and per-event reports
**Description.** Rollups over the same measures, plus trend and phase comparison.
The **per-event report is the primary commercial deliverable** to the organizer.
**Priority** P1 · **Complexity** M · **Actor** Organizer, Government
**Future.** Year-over-year comparison for the same moussem.

### RPT-005 — Per-zone report
**Description.** Occupancy and density curves, LOS band time-in-state, queue and
waiting times, alerts, incidents, coverage, capacity headroom.
**Priority** P1 · **Complexity** S · **Actor** Safety Officer
**Future.** Correlation of zone density-hours (`KPI-20`) against medical triage
load — the first quantitative evidence linking crowd density to injury rate at
this event.

### RPT-006 — Per-camera report
**Description.** Uptime, MTBF, tamper events, latency and FPS distributions,
detection-confidence trend, time spent uncalibrated, contribution to coverage.
**Business value.** Drives the maintenance programme and the next hardware
purchase, with evidence.
**Priority** P2 · **Complexity** S · **Actor** Administrator
**Future.** Failure prediction from health trends.

### RPT-007 — Per-operator and per-shift report
**Description.** Response latency, incidents owned and resolved, handover
completeness. **Supervisor and auditor visibility only** (`OPR-007`).
**Priority** P2 · **Complexity** S · **Actor** Supervisor
**Future.** Aggregate shift benchmarking rather than individual ranking.

### RPT-008 — Per-alert and per-rule report
**Description.** Fire rate, confirm rate, dismissal reason distribution, mean time
to acknowledge, demotions triggered (`ALM-008`).
**Business value.** The evidence base for tuning, and the honest answer to "how
often is your AI wrong?" — a question a government stakeholder will certainly ask
and which we must be able to answer with a number.
**Priority** P0 · **Complexity** S · **Actor** Engineering, Government
**Future.** Published per-rule performance in the product datasheet.

### RPT-009 — Per-incident report and after-action pack
**Description.** The full incident record: timeline, evidence manifest with
integrity hashes, notifications and their delivery receipts, configuration version
in force, after-action review (`INC-012`). Exported as a sealed, signed package.
**Business value.** This is the artifact that goes to the coroner, the prosecutor,
or the insurer. It must be complete and it must be tamper-evident.
**Priority** P0 · **Complexity** L · **Actor** Legal, Commander
**Future.** Jurisdiction-specific statutory report templates.

### RPT-010 — Crowd statistics report
**Description.** Occupancy, density, flow, queue and waiting times, heatmaps,
bottleneck history, peak analysis, evacuation-time estimates over the event.
**Priority** P1 · **Complexity** M · **Actor** Safety Officer, Government
**Future.** Comparison against the venue's approved crowd-management plan —
*did the event behave as the plan assumed?*

### RPT-011 — Horse and tbourida statistics report
**Description.** Horses on site by hour and zone, entries and exits, arena and
waiting-area utilization, runs per hour, run duration, inter-run interval, horses
per sorba, track clearance record, track incursion events, riderless-horse events.
**Business value.** The organizer's and the federation's report, and the safety
file for the equestrian programme. **The track-clearance record — every run, with
the verified-clear state at its start — is the document that answers the only
question that will be asked if a rider is killed.**
**Priority** P1 · **Complexity** M · **Actor** Organizer, Safety Officer
**Future.** Formation-quality analytics (`HRS-005` future work).

### RPT-012 — Parking and traffic statistics report
**Description.** Lot utilization curves, time-to-full, inflow and outflow by
approach, congestion episodes, emergency-route blockage events and durations.
**Priority** P1 · **Complexity** S · **Actor** Traffic Command
**Future.** Origin–destination flow matrices across gates, aggregate only.

### RPT-013 — Export formats and distribution
**Description.** PDF for signature, CSV and XLSX for analysis, and a machine
export for the client's own systems. Every export is audited (`AUD-004`).
**Priority** P1 · **Complexity** S · **Actor** All
**Future.** Scheduled distribution lists per agency.

---

## 13. Module 9 — Replay and Evidence (`RPL`)

> **This module is the reason the platform records video at all**, and it triggers
> a direct conflict with ADR 0004, which states that no imagery is persisted except
> alert snapshots. A 30-second pre-roll cannot come from a snapshot. It comes from
> a buffer that was already recording everyone, all the time.
>
> That conflict is resolved here, deliberately and on the record, rather than by
> quietly starting to record a million people while the README promises otherwise.
> **This module requires a new ADR and a Data Protection Impact Assessment before
> implementation** (§29, question 1).

### RPL-001 — Continuous recording buffer
**Description.** A bounded, encrypted-at-rest ring buffer of the raw camera
streams, retained for a configurable window (**default: 72 hours**), after which
frames are irrecoverably destroyed unless captured into a sealed segment
(`RPL-004`) or held (`RPL-009`).

Constraints, all binding:
- **No analytics of any kind are ever run over the recording buffer.** It is
  write-once, read-on-demand-by-a-human. Detection runs on the live stream and
  nowhere else. This is what prevents the buffer from becoming a retrospective
  surveillance corpus.
- Buffer access requires an explicit authorization and is **individually audited**
  (`AUD-004`), including the camera, the time range, and the requesting user.
- Retention is per-camera-configurable, and zones with heightened sensitivity —
  the prayer area, the medical tent — may be configured to **zero-retention**,
  where only alert snapshots exist.
- Encryption keys are managed separately from the storage, so an exfiltrated disk
  is inert.

**Business value.** Without pre-roll, an operator sees an alert and its aftermath,
never its cause. "What happened in the ten seconds before the crowd broke" is the
only question worth asking, and it is unanswerable from a snapshot.
**Priority** P0 · **Complexity** L · **Actor** System
**Future.** Selective retention — full rate on track and gate cameras, reduced
frame rate elsewhere, which cuts storage by an order of magnitude and narrows the
privacy exposure at the same time.

### RPL-002 — Alert and incident pre-roll
**Description.** Every alert and incident links to the buffer segment spanning
`T − 30s` (configurable) through the end of the condition. One click from the
alert queue.
**Business value.** Verification in seconds. Volume I's alert-quality programme
(`KPI-14`) depends on operators actually looking, and they will only look if it
costs one click.
**Priority** P0 · **Complexity** M · **Actor** Operator
**Future.** Pre-roll length varying by rule — a crush precursor wants two minutes,
a parking alert wants ten seconds.

### RPL-003 — Synchronized multi-camera replay
**Description.** Replay N cameras on one timeline, wall-clock synchronized.
Requires **NTP-disciplined camera clocks**; where a camera's clock is unsynchron-
ized, the platform must say so and must not silently align streams that are not
aligned.
**Business value.** An incident is rarely visible on one camera. Reconstructing it
across four requires that "14:22:07" mean the same instant on all four — and an
evidence pack built on unsynchronized clocks will be dismantled by opposing
counsel in five minutes.
**Priority** P1 · **Complexity** L · **Actor** Investigator
**Future.** Automatic clock-drift measurement and correction, with the correction
recorded in the evidence manifest.

### RPL-004 — Evidence segment capture and sealing
**Description.** Capture a time range from the buffer into an immutable **sealed
segment**: cryptographically hashed, the hash recorded in the append-only audit
log, with a manifest stating source camera, time range, clock-sync state,
configuration version, capture operator, and reason. Sealed segments are exempt
from buffer expiry.
**Business value.** Principle 2.4. The moment a frame may matter, it stops being
video and becomes evidence. Sealing at capture — not at export — is what makes the
chain of custody continuous.
**Priority** P0 · **Complexity** L · **Actor** Operator, Investigator
**Future.** Hash-chain anchoring to an external timestamping authority, so
integrity is provable even against a database administrator.

### RPL-005 — Chain of custody
**Description.** Every sealed segment carries a complete, append-only custody
record: created by, accessed by, exported by, transferred to, when, and under what
authority. Verifiable independently of the platform.
**Business value.** The first question defence counsel asks is who could have
altered this and when. There must be an answer.
**Priority** P0 · **Complexity** M · **Actor** Legal, Investigator
**Future.** Custody export in a standard law-enforcement interchange format, to be
identified with the client.

### RPL-006 — Clip export
**Description.** Export a sealed segment with a burned-in provenance overlay
(camera, timestamp, event, integrity hash) plus a sidecar manifest. **Export is a
privileged, dual-authorized action for any segment attached to a legal hold**, and
is always audited.
**Business value.** Evidence leaves the building in a controlled, attributable,
tamper-evident form — or it does not leave.
**Priority** P0 · **Complexity** M · **Actor** Investigator
**Future.** Optional automatic blurring of incidental faces on export. This
**obscures** faces; it does not detect or recognize them, and does not violate
ADR 0004.

### RPL-007 — Bookmarks and timeline annotation
**Description.** Operators bookmark moments during live monitoring or replay, with
a note, attributed and timestamped. Bookmarks appear on the incident timeline and
on the replay scrubber.
**Business value.** The operator who saw something at 21:14 must be able to mark
it in one keystroke, without leaving the live view. What they do not mark, nobody
will find later.
**Priority** P1 · **Complexity** S · **Actor** Operator
**Future.** Voice bookmarking.

### RPL-008 — Timeline navigation
**Description.** A unified event timeline overlaying alerts, incidents,
notifications, configuration changes, camera health transitions, rule arming
changes, phase transitions, and bookmarks. Scrub to any instant and see the venue
as the command center saw it.
**Business value.** **This is the after-action review instrument**, and it is the
single most persuasive thing the platform can demonstrate to a government
stakeholder. It answers "what did you know, and when did you know it" as a
navigable object rather than as a spreadsheet.
**Priority** P1 · **Complexity** L · **Actor** Investigator, Commander
**Future.** Replay of the full COP state — the map, the occupancy, the alerts — as
it stood at that instant, not merely the video.

### RPL-009 — Legal hold
**Description.** Per `INC-013`: suspend automatic deletion of all evidence
associated with an incident. Applying a hold is audited; **lifting one requires
two authorized users** and a recorded reason (`RBA-003`).
**Business value.** The reconciliation of a privacy obligation (delete promptly)
with a legal one (preserve evidence). Without it, the 30-day snapshot policy
destroys the record of a fatality four weeks before anyone requests it.
**Priority** P0 · **Complexity** M · **Actor** Legal, Security Officer
**Future.** Automatic proposed hold whenever an incident's casualty field is
populated.

### RPL-010 — Retention policy engine
**Description.** Central, auditable expression of every retention rule: buffer
window per camera, snapshot retention, telemetry rollup, audit retention, and
every hold that overrides them. Every automatic deletion writes an audit entry
recording what was destroyed and under which policy.
**Business value.** A privacy reviewer will ask to be shown, not told. **Deletion
must be as auditable as retention**, or the platform cannot prove it deleted
anything.
**Priority** P0 · **Complexity** M · **Actor** Security Officer
**Future.** Retention simulation — *"what will exist in 30 days?"*

---

## 14. Module 10 — GIS Mapping (`GIS`)

### GIS-001 — Venue base map with offline tiles
**Description.** A geo-referenced venue map with **self-hosted tiles**. The
command center must render its map with **no internet connectivity whatsoever.**
**Business value.** The venue is a field. Assuming a public tile service is
reachable — and that it will stay reachable when a hundred thousand phones saturate
the local cell — is how a command center goes blind at the worst moment. This is a
small requirement with a large failure mode, and it is invariably discovered on
opening day.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Drone-captured orthophoto of the venue as the base layer, which is far
more useful than a road map of an empty field.

### GIS-002 — Camera layer
**Description.** Each camera rendered at its GPS position with bearing, field-of-
view cone, **ground coverage polygon** (`CMG-013`), live health state, current
occupancy contribution, and active alerts.
**Business value.** Spatial situational awareness. Which cameras see the incident?
**Priority** P0 · **Complexity** M · **Actor** Operator, Commander
**Future.** Occlusion-aware viewshed from a structure model, replacing the
optimistic cone.

### GIS-003 — Zone layer
**Description.** Zone polygons rendered with live occupancy, density (persons/m²
with its LOS band colour), risk level, capacity headroom, active alerts, and
**calibration state**. An uncalibrated zone is visually distinct and never renders
a density colour.
**Business value.** The COP. One screen, whole venue, honest about what it knows.
**Priority** P0 · **Complexity** L · **Actor** All
**Future.** Ground-plane density heatmap as a continuous surface rather than a
per-zone fill.

### GIS-004 — Incident and alert layer
**Description.** Open incidents and unacknowledged alerts at their ground
coordinates, styled by severity and age, clustering at low zoom, one click to the
incident and to its live and recorded video.
**Priority** P0 · **Complexity** M · **Actor** Commander
**Future.** Responder positions, given a personnel-tracking integration.

### GIS-005 — Coverage and blind-spot map
**Description.** The venue rendered as three states: **observed** (a healthy,
calibrated camera covers this ground), **degraded** (covered only by a camera that
is uncalibrated, low-confidence, or in maintenance), and **blind**. Live, and
historical (`KPI-16`).
**Business value.** **The most honest artifact the platform produces.** No other
screen tells the event director what the system cannot see, and no competitor
ships one, because it makes the product look worse. It makes the product *trusted*,
which is worth more.
**Priority** P0 · **Complexity** L · **Actor** Commander, Government
**Future.** Camera-placement optimization against a target coverage.

### GIS-006 — Emergency route layer
**Description.** Emergency routes and evacuation routes as polylines with their
live clear/blocked state per segment (`OPS-010`), the blocking object, and its
dwell time.
**Business value.** The fire officer's standing question, answered on a map.
**Priority** P0 · **Complexity** M · **Actor** Civil Protection
**Future.** Live alternate-route computation that accounts for the current density
field, because a crowd does not evacuate along the lines a planner drew.

### GIS-007 — Flow and heatmap overlays
**Description.** Crowd flow vector field, dominant direction arrows, density
heatmap, and historical accumulation, all on the ground plane.
**Priority** P1 · **Complexity** M · **Actor** Safety Officer
**Future.** Time-lapse playback of the density field over the day.

### GIS-008 — Infrastructure and asset layer
**Description.** Gates, stalls, medical points, water, power, fencing, PA
coverage, radio dead zones, and marshalling points.
**Business value.** Answering "where is the nearest medical point to this
incident" requires knowing where medical points are. This layer is unglamorous and
gets skipped, and then the platform cannot answer the question.
**Priority** P1 · **Complexity** S · **Actor** Commander
**Future.** Nearest-resource routing.

### GIS-009 — Map annotation and sketching
**Description.** Commanders draw on the shared map: cordons, staging areas,
directions of approach. Annotations are attributed, timestamped, promotable to the
COP (§4.1), and replayable on the timeline (`RPL-008`).
**Business value.** How incident command actually communicates. The whiteboard is
the tool; the platform should be the whiteboard.
**Priority** P2 · **Complexity** M · **Actor** Commander
**Future.** Shared live cursors and multi-agency co-annotation.

---

## 15. Module 11 — Camera Calibration (`CAL`)

> Volume I §4.1 makes calibration a **precondition** of density, speed, occupancy
> de-duplication, and every crush-risk alert. It is therefore a precondition of the
> platform's central safety claim, and it is a *field workflow performed by a
> non-engineer under time pressure*, which is a very different design problem from
> a calibration script.

### CAL-001 — Ground-plane calibration workflow
**Description.** Guided per-camera workflow: the operator identifies four or more
surveyed ground reference points in the live image, enters or picks their venue
coordinates, and the platform solves the homography and displays the reprojection
error.
**Business value.** Without this, density is persons-per-frame, incomparable
between cameras, and no crush-risk threshold means anything (Volume I risk R-01).
**Priority** P0 · **Complexity** L · **Actor** Technician, Supervisor
**Future.** GNSS-tagged reference points captured on a phone during the site
survey and matched automatically.

### CAL-002 — Calibration quality assessment and acceptance
**Description.** Compute and display reprojection error, the effective ground area
covered, and the spatial distribution of error across the image. **A calibration
below the quality threshold cannot be accepted**, and a camera without an accepted
calibration cannot reach `commissioned` (`CMG-003`).
**Business value.** A bad calibration is more dangerous than none, because it
produces a confident, precise, wrong density. The gate must be structural.
**Priority** P0 · **Complexity** M · **Actor** Technician
**Future.** Per-region accuracy map, so the operator sees that the far end of the
frame is unreliable and the polygon should not extend there.

### CAL-003 — Ground-truth validation
**Description.** Verification against a known measurement: a marked distance on
the ground, or a person of known height at known positions. The platform reports
measured versus actual.
**Business value.** The homography can be self-consistent and wrong. Independent
validation is the only proof.
**Priority** P1 · **Complexity** M · **Actor** Technician
**Future.** Continuous self-validation against static ground features.

### CAL-004 — Calibration versioning and provenance
**Description.** Every calibration is versioned, attributed, timestamped, and
carries its validation record. Historical telemetry is interpreted under the
calibration in force at the time — **never re-interpreted under a later one.**
**Business value.** Last week's density figures must remain reproducible after the
camera is recalibrated. Retroactive reinterpretation of evidence is indefensible.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Automatic recomputation of historical aggregates as a *separate,
clearly-labelled* series, never overwriting the original.

### CAL-005 — Calibration invalidation
**Description.** A calibration is **automatically invalidated** by camera movement
(`CAM-008` tamper detection), by PTZ departure from the calibrated preset
(`CMG-005`), by lens or mount maintenance, or by a failed self-check. Invalidation
immediately suppresses that camera's ground-plane metrics and crush-risk alerts,
raises `ALR-36`, and degrades any dependent zone to `unknown`.
**Business value.** **This coupling is the most easily missed requirement in the
entire platform.** A camera nudged by a technician on a ladder silently turns every
density figure it produces into fiction. The platform must notice, and it must
notice on its own.
**Priority** P0 · **Complexity** M · **Actor** System
**Future.** Automatic re-calibration proposal from the pre-move reference features.

### CAL-006 — Calibration coverage dashboard
**Description.** Fleet-wide calibration state: calibrated, expired, invalidated,
never calibrated — with the consequent blind and degraded ground area (`GIS-005`).
**Business value.** Before the gates open, one screen answers "can this system be
trusted today?"
**Priority** P1 · **Complexity** S · **Actor** Administrator
**Future.** Pre-event readiness gate that blocks event activation below a coverage
threshold, overridable only with a recorded justification.

---

## 16. Module 12 — Configuration Management (`CFG`)

### CFG-001 — Immutable versioned configuration
**Description.** Every configuration change creates a new immutable version with
actor, timestamp, reason, and a diff against its predecessor. Nothing is edited in
place. Every alert and incident records the version in force when it was raised.
**Business value.** Principle 2.5. Six months later: *"what was the north gate
threshold at 21:47, who set it, when, and why?"* If the platform cannot answer
that, it cannot support an inquest, and its evidence is worth little.
**Priority** P0 · **Complexity** L · **Actor** System
**Future.** Configuration as a signed, exportable artifact for the event safety
file.

### CFG-002 — Scoped configuration hierarchy
**Description.** Global → event → zone → camera, with explicit precedence, and a
resolved-value view showing which level supplied each effective setting.
**Business value.** Replaces the prototype's process-global settings singleton. A
critical density in a prayer area is not a critical density in a food court, and
an operator must be able to see *why* a value is what it is.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Inherited-value warnings when an override silently masks a
safety-officer-approved default.

### CFG-003 — Change review and approval
**Description.** Safety-critical settings (`ZON-002`, escalation matrices,
retention policy, arming schedules) require review and approval by a distinct role
before taking effect. Non-critical settings apply immediately.
**Business value.** The blast radius of a mistyped density threshold is a crowd
crush that goes unalarmed. The blast radius of a mistyped queue-length warning is
a mildly annoyed supervisor. These must not have the same workflow.
**Priority** P0 · **Complexity** M · **Actor** Safety Officer
**Future.** Backtest a proposed change against yesterday's stream before approving.

### CFG-004 — Rollback
**Description.** Roll back to any prior configuration version in one audited
action. Rollback is a new version, not a deletion.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Automatic rollback proposal when a change is followed by an alert-rate
anomaly.

### CFG-005 — Configuration propagation and convergence
**Description.** Changes propagate to vision workers, the alert engine, and the
consumers within a bounded time. The platform **displays which components have
converged** and flags any that have not.
**Business value.** A zone polygon edited in the UI but not yet live in the worker
is a zone that is not actually being monitored the way the operator believes it is.
Silent divergence between intent and behaviour is the worst class of bug in a
safety system.
**Priority** P0 · **Complexity** M · **Actor** System
**Future.** Convergence SLO with alerting.

### CFG-006 — Secrets management
**Description.** Camera credentials, API keys, and certificates live in a secret
store. The platform holds references. **No secret is ever written to a log, a
configuration export, a database column, or a screen.**
**Business value.** RTSP URLs with embedded credentials are the single most
commonly leaked value in CCTV deployments.
**Priority** P0 · **Complexity** M · **Actor** Security Officer
**Future.** Automatic credential rotation.

---

## 17. Module 13 — Notification System (`NTF`)

> **Displaying an alert is not delivering it.** A critical alert rendered on a
> screen nobody was looking at has not been delivered, and the platform must know
> the difference (principle 2.2).

### NTF-001 — Channel abstraction
**Description.** Channels: in-console (visual and audible), desktop push, mobile
push, SMS, email, webhook, and radio/PA integration. Each channel declares its
**expected latency, its reliability, and whether it supports acknowledgement.**
**Business value.** SMS may take thirty seconds and may silently fail. Console
audio is instant but requires presence. Routing decisions must be made with these
properties, not despite them.
**Priority** P0 · **Complexity** L · **Actor** System
**Future.** TETRA / professional radio integration; PA announcement triggering,
always human-confirmed.

### NTF-002 — Routing policy
**Description.** Route by severity, incident category, zone, owning agency, event
phase, and on-call roster. Policies are versioned configuration (§16).
**Business value.** A medical incident reaches medical command, at 03:00, on the
channel they actually monitor.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Policy simulation against a historical alert stream before activation.

### NTF-003 — On-call rosters
**Description.** Per agency, per role, a rotating on-call schedule with overrides,
holidays, and a designated fallback that is never empty.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Integration with the agency's own rostering system.

### NTF-004 — Delivery tracking and receipts
**Description.** Every notification records dispatch, provider acceptance,
delivery receipt where the channel supports it, and human acknowledgement. Failed
delivery **automatically retries on an alternate channel.** The incident timeline
shows all of it.
**Business value.** "We sent an SMS" is not a defence at an inquest. "The SMS was
delivered at 21:47:12 and acknowledged at 21:47:31 by Commander X" is.
**Priority** P0 · **Complexity** L · **Actor** System
**Future.** Per-channel reliability statistics driving routing preference
automatically.

### NTF-005 — Escalation on non-acknowledgement
**Description.** An unacknowledged notification escalates on a per-severity timer:
another channel, then the supervisor, then the commander. **Escalation raises
awareness; it never silently reassigns ownership** (`INC-006`).
**Business value.** The failure mode of every alerting system ever built is the
alert nobody saw. The timer is the only defence.
**Priority** P0 · **Complexity** M · **Actor** System
**Future.** Escalation paths per incident category and per event phase.

### NTF-006 — Notification storm control
**Description.** Deduplication, rate limiting, and digest batching per recipient
per channel — bound to the alert clustering of `ALM-003`, so one problem produces
one notification. **`emergency` severity bypasses all of it.**
**Business value.** A platform that sends a government official four hundred SMS
messages in an hour has been permanently uninstalled. But the one message that
matters must always get through, which is why the bypass is absolute.
**Priority** P0 · **Complexity** M · **Actor** System
**Future.** Recipient-configurable digest windows.

### NTF-007 — Quiet hours and their limits
**Description.** Per-recipient quiet hours and channel preferences, which **never
apply to `critical` or `emergency` severity.**
**Business value.** Respect the recipient's sleep, right up to the moment that
respecting it would cost a life. The exception must be hard-coded, not configurable.
**Priority** P1 · **Complexity** S · **Actor** All
**Future.** —

### NTF-008 — Outbound webhooks and integrations
**Description.** Signed, retried, idempotent webhooks to external systems, with a
delivery log and a replay facility.
**Business value.** The dispatch system, the organizer's app, the traffic
authority. The platform must be a citizen of the client's landscape, not an island.
**Priority** P2 · **Complexity** M · **Actor** Administrator
**Future.** Inbound integrations: dispatch status, panic buttons, weather, traffic.

### NTF-009 — Broadcast to operators
**Description.** A supervisor or commander broadcasts a message to all consoles,
an agency, or a zone's assigned operators, with read receipts.
**Priority** P1 · **Complexity** S · **Actor** Commander
**Future.** Structured, acknowledged tasking rather than free text.

---

## 18. Module 14 — Audit Logging (`AUD`)

### AUD-001 — Append-only audit log
**Description.** Enforced **in the database**, not in the application: the
application role holds no `UPDATE` or `DELETE` grant on the audit table, and a
trigger raises on any attempt. **An attacker holding the `administrator` role
cannot erase their trail.**
**Business value.** This is the entire difference between an audit log and a log.
Accreditation reviewers test it directly.
**Priority** P0 · **Complexity** M · **Actor** Security Officer
**Future.** Hash-chain anchoring to an external authority, so tampering is
detectable even by a database administrator.

### AUD-002 — Audited action coverage
**Description.** Every authentication and session event; every mutation of
cameras, zones, users, roles, thresholds, arming, and retention; every alert
disposition; every incident transition; every notification dispatch and receipt;
every configuration version; every break-glass invocation; every legal hold and
its lifting; and **every access to imagery** — snapshots, buffer, sealed segments,
exports.
**Business value.** Imagery access is the one thing a privacy reviewer will
examine line by line.
**Priority** P0 · **Complexity** M · **Actor** System
**Future.** Coverage assertion test — a test that fails when a new mutating
capability ships without an audit entry.

### AUD-003 — Audit record content
**Description.** Actor, agency, role in force, timestamp (UTC, with the local
offset recorded), source IP, user agent, action, resource, before/after state,
result, and the configuration version.
**Priority** P0 · **Complexity** S · **Actor** System
**Future.** —

### AUD-004 — Imagery-access audit
**Description.** A dedicated, separately queryable view of every access to any
frame of any person: who, what camera, what time range, under what authority, for
what stated reason.
**Business value.** The platform's privacy claim (ADR 0004) is that it does not
surveil individuals. The recording buffer (`RPL-001`) is the one place where that
claim could be quietly broken by an insider. **This log is the control that makes
the claim enforceable rather than merely stated**, and it is the single most
important artifact in a Data Protection Impact Assessment.
**Priority** P0 · **Complexity** M · **Actor** Security Officer, Auditor
**Future.** Anomaly detection on access patterns — an operator reviewing footage
of a zone they are not assigned to, at a time no incident occurred.

### AUD-005 — Audit search and export
**Description.** Query by actor, resource, time, action, incident. Export sealed
and hashed for an investigation.
**Priority** P1 · **Complexity** S · **Actor** Auditor
**Future.** SIEM forwarding.

### AUD-006 — Audit integrity monitoring
**Description.** Continuous verification of the append-only constraint and of
sequence continuity. A gap is itself a `critical` alert.
**Priority** P1 · **Complexity** M · **Actor** Security Officer
**Future.** Independent off-box replica.

### AUD-007 — Audit retention
**Description.** Seven years, immutable, exempt from every other retention policy
and from every hold-lifting workflow.
**Priority** P0 · **Complexity** S · **Actor** Security Officer
**Future.** Cold-storage tiering.

---

## 19. Module 15 — System Administration (`ADM`)

### ADM-001 — Service and worker administration
**Description.** Inventory and control of vision workers, consumers, the alert
engine, and the media gateway: version, health, assigned cameras, restart, drain.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Rolling restart that never drains a track camera's worker.

### ADM-002 — Capacity planning
**Description.** Live and historical worker capacity: cameras per worker, analytic
FPS achieved versus target, headroom, and the measured bottleneck stage (ADR 0005).
**Business value.** Answers "can we add ten cameras?" with a measurement.
**Priority** P1 · **Complexity** M · **Actor** Administrator
**Future.** Procurement recommendation from the benchmark harness.

### ADM-003 — Backup and restore
**Description.** Scheduled, verified backups of configuration, incidents, audit,
and telemetry. **Restore is tested, on a schedule, and the test result is
recorded.** An untested backup is a rumour.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Point-in-time recovery.

### ADM-004 — Disaster recovery and degraded operation
**Description.** Documented, drilled, and *implemented* behaviour for: database
loss, Redis loss, worker loss, network partition, total server loss. Each is
specified in §21.
**Business value.** Principle 2.2. The event proceeds whether or not the software
does.
**Priority** P0 · **Complexity** L · **Actor** Administrator
**Future.** Automated failover with a standby command post.

### ADM-005 — Licensing, SBOM, and compliance posture
**Description.** Per-build CycloneDX SBOM, license gate (deny AGPL/GPL/SSPL per
ADR 0002), CVE scanning, and a signed compliance pack for procurement.
**Priority** P1 · **Complexity** M · **Actor** Security Officer
**Future.** Continuous compliance attestation.

### ADM-006 — Time synchronization
**Description.** NTP discipline across servers and cameras; continuous drift
measurement; **clock-sync state is a first-class health signal** and is recorded in
every evidence manifest (`RPL-003`).
**Business value.** Every timeline, every correlation, and every piece of evidence
rests on the assumption that "21:47:12" means the same instant everywhere. It is
routinely false, and the failure is invisible until an evidence pack is challenged.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** GNSS-disciplined local stratum-1 source, since the venue may have no
reliable internet (`GIS-001`).

### ADM-007 — Localization, time zone, and calendar
**Description.** UI in French, Arabic, and English, with **right-to-left layout**.
All timestamps stored UTC, displayed in venue-local time with the offset shown.
Support for the Hijri calendar alongside the Gregorian, and for prayer-time
computation.
**Business value.** The operators are Moroccan. An English-only command center
staffed under stress by French- and Arabic-speaking officers is a safety hazard,
not a localization backlog item.
**Priority** P1 · **Complexity** L · **Actor** All
**Future.** Darija terminology review with actual operators, not translators.

---

## 20. Module 16 — Health Monitoring (`HLT`)

### HLT-001 — Platform health surface
**Description.** Operator-facing rendering of Volume I `SYS-001`…`SYS-012`: CPU,
GPU (including thermal throttle), RAM, disk, database, Redis, workers, bus lag,
API latency, WebSocket connections, active operators.
**Priority** P0 · **Complexity** M · **Actor** Administrator
**Future.** Predictive alerting on trend rather than threshold.

### HLT-002 — Observability posture (venue coverage)
**Description.** `SYS-011` surfaced as a headline figure and as the blind-spot map
(`GIS-005`): what fraction of the venue is currently observed by a healthy,
calibrated camera?
**Business value.** **The most honest number in the platform**, and the one that
gates the credibility of every other number on the screen.
**Priority** P0 · **Complexity** M · **Actor** Commander, Government
**Future.** Coverage SLO per zone risk level, with a pre-event readiness gate.

### HLT-003 — Health alerting and self-alarm
**Description.** The platform alerts on its own degradation (`ALR-31`…`ALR-41`),
through the same queue, routing, and escalation as any operational alert.
**Business value.** A monitoring system with a separate, quieter channel for its
own failures will not be watched.
**Priority** P0 · **Complexity** S · **Actor** System
**Future.** —

### HLT-004 — Synthetic monitoring
**Description.** End-to-end probes that continuously verify the whole chain: inject
a synthetic detection, confirm an alert is raised, delivered, and rendered.
Measures the Volume I §15.4 latency budget in production, continuously.
**Business value.** Every component can report healthy while the chain is broken.
The only way to know the platform works is to make it work, repeatedly, on purpose.
**Priority** P1 · **Complexity** M · **Actor** System
**Future.** Synthetic incursion drill on the track camera between runs.

### HLT-005 — Pre-event readiness check
**Description.** A single gate before event activation: cameras commissioned and
calibrated, coverage above threshold, thresholds signed off, rosters staffed,
notification channels test-delivered, backups verified, clocks synchronized.
Produces a signed readiness report. Failures are overridable **only with a recorded
justification by the safety officer.**
**Business value.** Every catastrophe in this class of system is preceded by a
checklist item nobody checked. This is the checklist, and the platform runs it.
**Priority** P0 · **Complexity** M · **Actor** Safety Officer
**Future.** Automatic scheduling 24 hours before gates open.

---

## 21. Module 17 — Dashboard and Widgets (`DSH`)

### DSH-001 — Role-based dashboard composition
**Description.** Dashboards are composed of widgets, laid out per role and per
agency, saved as versioned configuration. A commander's screen is not an
administrator's.
**Priority** P1 · **Complexity** M · **Actor** All
**Future.** Per-operator personalization within role-permitted bounds.

### DSH-002 — Widget catalogue
**Description.** Live camera tile and grid; GIS map; alert queue; incident board;
zone status board; KPI tiles (occupancy, density, flow, queue time); people,
vehicle, and horse counters; **track clearance state**; system and camera health;
coverage figure; timeline; weather; clock (venue-local, with UTC available);
programme and phase; operator roster and span-of-control; report shortcuts;
notification log; search.
**Priority** P1 · **Complexity** L · **Actor** All
**Future.** Widget SDK for client-specific extensions.

### DSH-003 — Video wall mode
**Description.** A large-format, non-interactive display: cameras, map, critical
alerts, coverage, and the track state. Auto-cycling. **Failure of the wall must
never affect the consoles.**
**Business value.** Shared situational awareness in the room.
**Priority** P1 · **Complexity** M · **Actor** All
**Future.** Automatic slew of a wall tile to the camera covering a new critical
incident.

### DSH-004 — Attention management
**Description.** Critical alerts interrupt; warnings queue; info accrues. Audible
alerting is **distinct per severity** and cannot be muted for `emergency`. The
platform is deliberately parsimonious with the operator's attention (principle 2.6).
**Business value.** Attention is the scarcest resource in the room. Spending it is
the platform's central design responsibility, and every widget that blinks for no
reason is a withdrawal from an account that pays for the track incursion alert.
**Priority** P0 · **Complexity** M · **Actor** Operator
**Future.** Measured attention cost per widget, from `KPI-18` response latency.

### DSH-005 — Search
**Description.** Unified search across cameras, zones, incidents, alerts, and
timeline moments.
**Priority** P2 · **Complexity** M · **Actor** All
**Future.** Natural-language time-range query over the operational record. **Never
over imagery of people.**

### DSH-006 — Degraded-mode display
**Description.** When any dependency fails, the dashboard states plainly what is
now unknown and what is stale, and how old the last good value is. It **does not
keep rendering the last known value as though it were live.**
**Business value.** Principle 2.7. A frozen occupancy figure that still looks live
is the most dangerous single pixel the platform can draw.
**Priority** P0 · **Complexity** M · **Actor** All
**Future.** Automatic degraded-mode drill during pre-event readiness.

---

## 22. Module 18 — Public Safety Operations (`PSO`)

> Command actions, not observations. Everything here is initiated by a human with
> the authority to cause a physical consequence (principle 2.3). The platform's
> role is to inform the decision, record it, coordinate it, and evidence it.

### PSO-001 — Evacuation management
**Description.** Declare an evacuation, venue-wide or per zone. Switches phase,
re-arms egress rules, flips counting semantics to "persons remaining," publishes
route status, notifies every agency, and drives the wall display.
**Business value.** The moment of highest consequence in the platform's life. It
must be one deliberate action, not fourteen screens.
**Priority** P0 · **Complexity** L · **Actor** Incident Commander
**Future.** Route recommendation from the live density field, not the static plan —
because the crowd will not evacuate along the lines a planner drew.

### PSO-002 — Evacuation progress monitoring
**Description.** Live persons remaining per zone and venue-wide, egress rate per
gate, blocked-route status, projected time to clear, and zones not decreasing.
**Business value.** During an evacuation the only question is "who is still in
there, and why isn't that number falling?"
**Priority** P0 · **Complexity** M · **Actor** Commander
**Future.** Zone-level clearance confirmation by a steward, reconciled against the
system's estimate. **Where they disagree, the human wins and the discrepancy is
logged.**

### PSO-003 — Crowd hold and release
**Description.** Command-directed holding of a crowd upstream of a bottleneck, and
its controlled release. Records the decision, its author, its duration, and the
downstream density that justified it.
**Business value.** The standard intervention for an ingress crush, and one that
must be evidenced afterwards.
**Priority** P1 · **Complexity** M · **Actor** Commander
**Future.** Release-rate recommendation from measured downstream capacity.

### PSO-004 — Gate and zone closure
**Description.** Command closure of a gate or zone, propagated to zone state
(`ZON-006`), alert arming, signage, and every agency's COP.
**Priority** P1 · **Complexity** S · **Actor** Commander
**Future.** Automatic redirect capacity computation for the remaining gates.

### PSO-005 — Mass-casualty mode
**Description.** Elevates the platform's posture: medical incident category
default, triage-load display, medical-route clearance foregrounded, notification
escalation shortened, all non-critical alerting demoted.
**Business value.** In a mass-casualty incident the platform must get out of the
way of the people responding, while keeping the routes clear and the record intact.
**Priority** P2 · **Complexity** M · **Actor** Commander
**Future.** Casualty-count field feeding statutory reporting.

### PSO-006 — Lost-person operations
**Description.** Workflow around the `PPL-021` advisory and around manually
reported missing persons: log, describe (**description recorded as free text by a
human; the platform performs no matching and no search over imagery**), task
stewards, coordinate zone sweeps, and record reunification.
**Business value.** The most common real incident at a family event, and the one
the platform is most tempted to solve with face recognition. **It does not.** It
coordinates humans, which is what actually works and what ADR 0004 requires.
**Priority** P2 · **Complexity** M · **Actor** Operator
**Future.** Steward mobile app tasking. Reunification purges the advisory and its
snapshot immediately, ahead of the retention boundary.

### PSO-007 — VIP and protected-movement support
**Description.** Route clearance verification along a planned movement corridor,
zone state coordination, and time-boxed restricted-area arming.
**Business value.** Protocol movements are planned; the platform verifies the plan
is met.
**Priority** P2 · **Complexity** M · **Actor** Police
**Future.** None. **Note:** corridor verification is zone-and-time based. The
platform never identifies the protected person, or anyone else.

### PSO-008 — Multi-agency coordination board
**Description.** The shared COP (§4.1) with agency presence, current commanders,
active incidents by agency, cross-agency transfers pending acceptance, and shared
map annotations.
**Business value.** Divergent situational pictures are how agencies work at cross
purposes. One board, one picture, private notes preserved.
**Priority** P1 · **Complexity** L · **Actor** All agencies
**Future.** Federated boards across neighbouring venues and the regional command.

### PSO-009 — Drill and exercise mode
**Description.** Run the platform against recorded or synthetic data in a mode
that is **unmistakably and irrevocably marked as an exercise** — in the UI, in
every notification, in every audit entry, in every generated report. Exercise data
can never be promoted to live records.
**Business value.** Operators must train before the event. An exercise notification
mistaken for a real one, or a real one mistaken for an exercise, is a catastrophe
in both directions. The marking must be structural, not a banner.
**Priority** P1 · **Complexity** M · **Actor** Safety Officer
**Future.** Scenario library; scored exercises feeding operator competence
(`OPR-001`).

---

## 23. Module 19 — Horse Arena Operations (`HAO`)

> The operational surface over Volume I's `HRS` module. Everything here exists to
> get a human decision made correctly in the seconds around a charge.

### HAO-001 — Track state board
**Description.** A single, unambiguous, large-format display of the charge track:
`cleared` / `staged` / `charging` / **`unknown`** — and, distinctly, the
positively-asserted clearance state of `HRS-007`. **The absence of an alert is
never rendered as `clear`.** Any track camera degraded, uncalibrated, or offline
forces `unknown`.
**Business value.** The instrument the track marshal does not currently have.
**The distinction between "no alert" and "verified clear" is the entire feature**,
and a system that renders `clear` from a dead camera has killed someone.
**Priority** P0 · **Complexity** M · **Actor** Track Marshal, Commander
**Future.** A physical go/no-go indicator at the start line, driven from this state.

### HAO-002 — Pre-run clearance workflow
**Description.** A structured sequence before each run: track verified clear for T
seconds, all track cameras healthy and calibrated, operator assigned (`OPR-005`),
smoke rule disarm scheduled and visible (`ALM-004`), marshal confirmation.
Recorded per run, for every run.
**Business value.** This record — every run, with its verified-clear state at the
start — **is the document that answers the only question that will be asked if a
rider is killed.** It is generated automatically, forty times a day, at no cost.
**Priority** P0 · **Complexity** M · **Actor** Track Marshal
**Future.** Blocking integration with the start signal, under a formal safety case.

### HAO-003 — Incursion response
**Description.** On `ALR-01` (track incursion while charging): the highest-severity
interrupt on every console and the wall, the ground coordinate, the camera, the
sealed pre-roll, and a one-action escalation to the marshal's radio.
**Business value.** The 400 ms latency budget (Volume I §15.4) is spent by the time
this reaches the screen. Every subsequent millisecond is a design failure.
**Priority** P0 · **Complexity** M · **Actor** Operator, Marshal
**Future.** Direct track-side hardware interlock (Phase 4).

### HAO-004 — Rider-down protocol
**Description.** The operational surface of `HRS-017`: on a riderless-horse or
high-confidence incident on the track, hold the track at `no-go`, create a medical
incident pre-populated with the location and sealed pre-roll, notify medical
command, and require an explicit marshal clear-down before `HAO-001` may return to
verified clear.
**Business value.** Converts a detection into a response. The value of seeing a
fall is entirely in the next twenty seconds.
**Priority** P0 · **Complexity** M · **Actor** Marshal, Medical
**Future.** Direct dispatch integration.

### HAO-005 — Run log
**Description.** Every run: start and end, duration, horses detected, riders,
clearance state at start, incursions, riderless events, smoke-rule arming
transitions, spectator density in the adjacent zones throughout.
**Business value.** The safety file for the equestrian programme, and the evidence
base for `RPT-011`. Also the first data anyone will have on whether spectator
density peaks dangerously in the minutes before each run.
**Priority** P1 · **Complexity** M · **Actor** Organizer, Safety Officer
**Future.** Formation-quality analytics.

### HAO-006 — Horse zone operations
**Description.** Live occupancy and density of arena, waiting area, and picket
lines against capacity; horse–crowd buffer state (`HRS-015`); loose-horse alert
handling; horse entry and exit reconciliation against the troop manifest.
**Priority** P1 · **Complexity** M · **Actor** Operations
**Future.** Welfare indicators — rest dwell time per picket area.

### HAO-007 — Programme integration
**Description.** The run schedule from `EVT-003` drives smoke-rule arming, track
risk elevation, operator coverage requirements, and spectator-zone thresholds.
**A run detected off-schedule (`HRS-011`) is itself an alert** — either the
programme is wrong or something is happening that should not be.
**Priority** P1 · **Complexity** M · **Actor** Supervisor
**Future.** Automatic reconciliation of the planned against the observed programme.

---

## 24. Module 20 — Parking Operations (`PKO`)

### PKO-001 — Parking board
**Description.** Per lot: occupancy, capacity, remaining, inflow rate, projected
time-to-full, state (`open`/`filling`/`full`/`closed`).
**Priority** P1 · **Complexity** S · **Actor** Traffic Command
**Future.** Public-facing availability feed.

### PKO-002 — Lot state management and diversion
**Description.** Command actions: close a lot, open an overflow lot, publish a
diversion. Diversion decisions are recorded with the occupancy that justified them.
**Business value.** Diverting *before* a lot fills is the difference between an
orderly redirect and a blocked access road with no room to turn around.
**Priority** P1 · **Complexity** M · **Actor** Traffic Command
**Future.** Automatic diversion recommendation to the nearest lot with headroom.

### PKO-003 — Access-road monitoring
**Description.** Approach-road vehicle flow, density, congestion state, wrong-way
events, and queue-tail position relative to the public highway.
**Business value.** A queue tail that reaches the highway is a matter for the
traffic authority, and they need warning, not notification.
**Priority** P1 · **Complexity** M · **Actor** Traffic Command
**Future.** Upstream junction notification.

### PKO-004 — Emergency-route enforcement in parking
**Description.** Continuous clear/blocked state of every emergency lane within
parking areas; illegal-parking alerts escalated to `critical` when on a route
(`ALR-20`); work-order dispatch to move the vehicle.
**Business value.** Parking areas are where emergency routes are blocked, and it is
never noticed until an ambulance cannot pass.
**Priority** P0 · **Complexity** M · **Actor** Traffic Command
**Future.** Steward mobile dispatch with the vehicle's location and a photograph.

### PKO-005 — Horse-transport and service-vehicle handling
**Description.** Designated lanes and areas for horse transport and service
vehicles, with **time-window-based permission** rather than identity-based
(ADR 0004 — no plate reading). A vehicle in a restricted lane outside its window
alerts.
**Priority** P2 · **Complexity** M · **Actor** Operations
**Future.** Trailer detection (`HRS-014`) once a custom dataset exists.

### PKO-006 — Parking statistics and reporting
**Description.** Utilization curves, turnover, time-to-full, congestion episodes,
route-blockage durations. Feeds `RPT-012`.
**Priority** P2 · **Complexity** S · **Actor** Organizer
**Future.** Capacity planning for next year's event.

---

## 25. Cross-cutting: degraded operation

Principle 2.2, made concrete. Each failure has a **specified**, implemented, and
drilled behaviour — not a hope.

| Failure | Behaviour | Never |
|---|---|---|
| **Database unavailable** | Detection and alerting continue. Alerts buffer on the event spine. Dashboard reads go stale and **say so**. Writes queue. | Detection stops. Alerts are lost. |
| **Redis / event spine unavailable** | Workers buffer locally and back-pressure. Alerting degrades to per-worker local rules for `emergency` severity only. | Silent alert loss. |
| **Vision worker lost** | Its cameras go `offline`, its zones go `unknown`, coverage drops visibly, the scheduler re-homes cameras with **track cameras first**. | A zone rendering `clear` from a dead worker. |
| **Media gateway lost** | No live video. **All analytics, counts, alerts, and incident workflow continue.** Operators are told video is unavailable. | The platform going down with the video. |
| **Network partition (venue ↔ command post)** | Local console operates from the last known COP, clearly marked stale, with local incident capture that reconciles on reconnect. | Presenting stale state as live. |
| **Total platform loss** | Documented paper fallback: printed zone map, radio protocol, manual incident log. Drilled before the event. | The event's safety depending on our uptime. |
| **Operator console crash** | Session preserved; incidents remain owned; unacknowledged critical alerts escalate on the `NTF-005` timer. | Ownership silently vanishing with the browser tab. |
| **GPU throttled or overloaded** | Analytic FPS is shed **by camera priority**; track cameras never shed; the shed is announced (`ALR-38`) and displayed. | Silent degradation of the detection rate. |
| **Clock desynchronization** | Affected cameras marked; evidence manifests record the sync state; multi-camera replay refuses to silently align them. | An evidence pack built on unaligned clocks. |

---

## 26. Non-functional requirements

| # | Requirement | Target | Rationale |
|---|---|---|---|
| NFR-01 | Critical alert, glass-to-operator | ≤ 400 ms p99 | Volume I §15.4. A safety parameter. |
| NFR-02 | Command-center availability during event hours | ≥ 99.9% | ~30 s/day of downtime. |
| NFR-03 | Recording buffer durability | No loss on single-disk failure | Evidence. |
| NFR-04 | Audit-log durability | No loss, ever; append-only | Accreditation. |
| NFR-05 | Dashboard interaction latency | ≤ 100 ms p95 | Operator attention. |
| NFR-06 | Live video latency (WebRTC) | ≤ 500 ms | Watching a crowd surge. |
| NFR-07 | Configuration convergence to workers | ≤ 5 s p99 | `CFG-005`. |
| NFR-08 | Concurrent operators | ≥ 50 per venue | Multi-agency. |
| NFR-09 | Cameras per venue | ≥ 200, horizontally scaled | ADR 0005; capacity measured, not asserted. |
| NFR-10 | Data at rest | Encrypted; keys separately managed | Exfiltrated disk is inert. |
| NFR-11 | Data in transit | TLS 1.3; mTLS between services | — |
| NFR-12 | Recovery point objective | ≤ 5 minutes | — |
| NFR-13 | Recovery time objective | ≤ 15 minutes | — |
| NFR-14 | Accessibility | WCAG 2.1 AA; colour never the sole severity carrier | Colour-blind operators exist; severity must survive a monochrome wall display. |
| NFR-15 | Localization | French, Arabic (RTL), English | The operators are Moroccan. |

---

## 27. Roadmap

Continuing the phase model of Volume I. Phase 2 remains **the deployable event
system**; nothing outside it is built until it is done.

### Phase 2 — MVP: the safety core

Camera management (`CMG-001`, `003`, `006`, `007`, `008`, `009`, `012`, `013`);
calibration (**all of `CAL`** — the gating dependency of Volume I risk R-01);
zones (`ZON-001`…`003`, `005`…`007`); alerts (`ALM-001`…`005`, `007`, `008`);
incidents (`INC-001`…`008`, `013`); operators (`OPR-002`, `003`, `005`, `006`);
roles (`RBA-001`…`005`); events (`EVT-001`…`006`); **replay and evidence
(`RPL-001`…`006`, `009`, `010`)** — gated on the DPIA of §29 question 1; GIS
(`GIS-001`…`006`); configuration (**all of `CFG`**); notifications
(`NTF-001`…`007`); audit (**all of `AUD`**); health (`HLT-001`…`003`, `005`);
dashboard (`DSH-001`…`004`, `006`); public safety (`PSO-001`, `002`, `009`);
horse arena (**all of `HAO`**); parking (`PKO-001`, `004`); reporting
(`RPT-001`…`003`, `009`, `011`).

*Exit criteria:* the pre-event readiness check (`HLT-005`) passes on real hardware
at the real venue; every degraded-mode row in §25 is demonstrated by fault
injection; the evidence chain (`RPL-004`→`RPL-006`) is validated by the client's
legal counsel; shift handover (`OPR-006`) is exercised by real operators.

### Phase 3 — Production

Multi-agency (`RBA-006`, `007`, `PSO-008`); full reporting; `RPL-003`, `RPL-007`,
`RPL-008`; `GIS-007`…`009`; `INC-009`…`012`; `PSO-003`…`007`; `HLT-004`;
`ADM-001`…`007`; `DSH-005`; remaining `PKO`, `HAO`, `ZON`, `EVT`; ONVIF
(`CMG-002`), PTZ (`CMG-005`); localization; SSO federation.

### Phase 4 — Enterprise

Multi-venue federation; `HRS-006` hardware interlock under a formal safety case;
webhook and dispatch integrations; steward mobile app; scenario library and scored
exercises; predictive capacity and diversion; SOC 2 / ISO 27001; independent
security accreditation and a completed DPIA.

---

## 28. Risk register (this volume)

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **O-01** | **Continuous recording (`RPL-001`) proceeds without a DPIA and an ADR**, contradicting ADR 0004 in practice while the README denies it | Medium | **Existential** — the platform's central claim, and its licence to operate | Blocking open question §29.1. No buffer implementation begins before ADR 0011 and a DPIA are signed. `AUD-004` imagery-access audit is the enforcing control. |
| **O-02** | Legal hold not built before the first event; a fatality's evidence is auto-deleted at 30 days | Medium | **Severe** | `INC-013` / `RPL-009` are P0 in Phase 2. Not negotiable. |
| **O-03** | Operators reject the platform because manual incident creation is missing or slow | High | Severe — the platform is abandoned and its record becomes a biased sample of only what cameras caught | `INC-004` is P0. Test with real stewards in Phase 2. |
| **O-04** | Shift handover never built; suppressions and disarmed rules become invisible blind spots overnight | **High** | Severe | `OPR-006` is P0. Every suppression has a mandatory expiry (`ALM-005`). |
| **O-05** | Clock desynchronization discovered when an evidence pack is challenged | Medium | Severe | `ADM-006` is P0; sync state in every manifest; `RPL-003` refuses silent alignment. |
| **O-06** | Map tiles depend on internet; command center goes blind when the cell network saturates | **High** | High | `GIS-001` self-hosted tiles, P0. |
| **O-07** | Notification storm sends a government official 400 SMS; platform is uninstalled | Medium | High | `NTF-006`, bound to `ALM-003` clustering. `emergency` always bypasses. |
| **O-08** | Calibration invalidation coupling (`CAL-005`) is missed; a nudged camera silently produces fictional density | Medium | **Severe** | `CAL-005` is P0 and is a fault-injection test case, not a code review item. |
| **O-09** | Break-glass is too hard, so credentials are shared | Medium | High | `RBA-006`: never blocked, always loud, always reviewed. |
| **O-10** | Scope pressure to add face recognition "for the lost-child feature" or "for the police" | **High** | **Existential** | ADR 0004 is architectural. `PSO-006` solves the operational need by coordinating humans. The refusal is the product. |
| **O-11** | Exercise notifications mistaken for real ones, or the reverse | Medium | Severe | `PSO-009`: exercise marking is structural and irrevocable, in the UI, notifications, audit, and reports. |

---

## 29. Open questions for the client

**Blocking.**

1. **May the platform continuously record video?** (`RPL-001`, risk O-01.) A
   30-second pre-roll requires it. This requires a new ADR and a **Data Protection
   Impact Assessment**, and it must be answered before any implementation.
   Sub-questions: buffer retention window (default 72 h); zero-retention zones
   (prayer area, medical tent); who may authorize buffer access; whether the
   recording is disclosed to the public and how.
2. **Who is the accountable safety officer**, empowered to sign off zone
   capacities, LOS thresholds, and escalation matrices (`EVT-006`, `ZON-002`)?
3. **What is the retention obligation for evidence**, and who may apply and lift a
   legal hold (`RPL-009`, `RBA-003`)?
4. **Which agencies will use the platform**, with what authority, and what may each
   see of the others' incidents (§4)?

**Important.**

5. Is there a national civil-protection incident taxonomy to align `INC-009` to?
6. What identity provider must the platform federate with (`RBA-004`)?
7. What radio, dispatch, or PA systems exist for `NTF-001` and `NTF-008`?
8. What is the venue's network and power provision at the command post, and is
   there a documented paper fallback today (§25)?
9. What are the operators' working languages, and who will validate the Arabic and
   Darija terminology (`ADM-007`)?
10. Who is the platform's counterparty for evidence handover — police, gendarmerie,
    prosecutor — and in what format do they require it (`RPL-006`)?

---

## 30. Architectural decisions to be promoted

This document implies decisions that belong in the ADR record before implementation:

| ADR | Subject | Why it is architectural |
|---|---|---|
| **0008** | Ground-plane calibration as a precondition (Volume I §4.1) | Gates every safety alert; changes the camera lifecycle. |
| **0009** | Contextual alert arming (Volume I §4.3) | Introduces the programme as a system input; alters the alert engine. |
| **0010** | Security Incident Detection replaces behavioural classification (Volume I §9) | A privacy commitment enforced in structure. |
| **0011** | **Continuous recording buffer, evidence sealing, and legal hold** (§13) | **Directly qualifies ADR 0004.** Blocking; requires a DPIA. |
| **0012** | Multi-agency model: common operating picture, private working space, four-axis authorization (§4) | Reshapes the identity and data model. |
| **0013** | Immutable versioned configuration; alerts and incidents reference their config version (§16) | Prerequisite for evidentiary integrity. |
| **0014** | Alert and incident are distinct domain objects (principle 2.1) | The core domain model of this volume. |

---

*End of Volume II. Reviewed against ADR 0001–0007 and the Detection & Analytics
SRS. No decision in this document supersedes an existing ADR, with one explicit
exception: §13 (`RPL-001`) qualifies ADR 0004's imagery-retention position and is
therefore blocked pending ADR 0011 and a Data Protection Impact Assessment.*
