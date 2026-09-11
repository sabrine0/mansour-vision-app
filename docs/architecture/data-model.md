# Data Model

PostgreSQL 16 + TimescaleDB. Every table below maps to the specification's table
list; where the mapping is not one-to-one, the reason is given.

## Design rules

1. **Configuration and telemetry are separated.** Configuration tables
   (`cameras`, `zones`, `users`) are small, mutable, and read constantly.
   Telemetry tables (`camera_ticks`, `crossings`, `zone_ticks`) are enormous,
   append-only, and never updated. They are TimescaleDB **hypertables** with
   retention and continuous-aggregate policies. Putting them in the same
   physical shape would make both slow.
2. **No table stores an identifier of a person.** There is no `track_id` column
   anywhere in this schema. See [ADR 0004](../adr/0004-no-biometric-inference.md).
3. **Soft-delete configuration, never telemetry.** A deleted camera must not
   orphan a year of history, so `cameras.deleted_at` is nullable and history
   references it by immutable `id`.
4. **All timestamps are `TIMESTAMPTZ` in UTC.** The prototype's naive-UTC
   convention was correct for SQLite, which has no timezone type. PostgreSQL
   does; we use it.

---

## Identity and access

### `users`
`id` · `email` (unique, citext) · `full_name` · `password_hash` (Argon2id) ·
`is_active` · `mfa_secret` (nullable) · `last_login_at` · `failed_login_count` ·
`locked_until` · `created_at` · `updated_at`

Passwords are Argon2id, never bcrypt-with-a-shrug. `failed_login_count` and
`locked_until` implement lockout; rate limiting at the edge is not sufficient
because it is per-IP, and credential stuffing is not.

### `roles`, `permissions`, `role_permissions`, `user_roles`
Classic RBAC, normalized. Permissions are string-typed as
`resource:action` (`camera:read`, `alert:acknowledge`, `zone:write`,
`user:manage`, `audit:read`). Roles ship seeded: `viewer`, `operator`,
`supervisor`, `admin`, `auditor`.

`auditor` is deliberately separate from `admin`: an auditor can read the audit
log and nothing else, and an admin **cannot** delete audit entries. Accreditation
reviewers ask for exactly this.

### `sessions`
`id` · `user_id` · `refresh_token_hash` · `issued_at` · `expires_at` ·
`revoked_at` · `ip` · `user_agent`

Access tokens are short-lived JWTs and are *not* stored. Refresh tokens are
stored **hashed**, so a database compromise does not yield usable sessions.
Logout and forced-revocation work by writing `revoked_at`.

---

## Venue configuration

### `cameras`
`id` · `name` · `zone_id` (nullable, primary zone) · `source_url` (secret-ref, not
plaintext) · `protocol` (`rtsp`|`onvif`|`usb`|`file`) · `latitude` · `longitude` ·
`heading_degrees` · `status` · `resolution_w/h` · `target_analytic_fps` ·
`worker_id` (nullable, assigned by the scheduler) · `recording_enabled` ·
`retention_days` · `deleted_at` · timestamps

RTSP URLs contain credentials. `source_url` holds a reference into the secret
store (Docker secret / Vault path), never the credential itself. This is the
single most commonly leaked value in CCTV platforms.

### `zones` — semantic, venue-level
`id` · `name` · `kind` (enum: `entrance`, `exit`, `emergency_exit`, `parking`,
`restricted`, `arena`, `waiting`, `medical`, `checkpoint`, `pedestrian_only`,
`vip`, `stage`, `food_court`, `market`, `prayer`, `general`) ·
`max_occupancy` · `risk_level` · `gps_polygon` (geography) · timestamps

### `camera_zones` — geometric, camera-level
`id` · `camera_id` · `zone_id` · `polygon` (normalized image coordinates, JSONB)

**Why the split.** One logical zone ("Parking North") is observed by several
cameras, each seeing a different part of it from a different angle. Occupancy is
a property of the *zone*; the polygon is a property of the *(camera, zone)* pair.
Collapsing these — as the specification's "Assigned Cameras" field implies —
makes overlapping-coverage de-duplication ([ADR 0006](../adr/0006-dwell-time-without-tracking-people.md))
impossible to express. See [ADR 0003](../adr/0003-static-infrastructure-is-configuration-not-detection.md).

### `counting_lines`
`id` · `camera_id` · `zone_id` (nullable) · `name` · `x1,y1,x2,y2` (normalized) ·
`inward_side` (`left`|`right`) · `enabled`

Multiple lines per camera, per the specification. Direction polarity is explicit
rather than implied by endpoint order — the prototype's convention ("in = right of
the vector p1→p2") is correct but has caused confusion; naming it removes the
ambiguity.

### `settings`
`key` · `value` (JSONB) · `scope` (`global`|`camera`|`zone`) · `scope_id` ·
`updated_by` · `updated_at`

Replaces the prototype's process-global `Settings` singleton. Thresholds are
per-zone, because a critical density in a prayer area is not a critical density
in a food court.

---

## Telemetry (TimescaleDB hypertables)

### `camera_ticks` — 1 Hz per camera
`time` · `camera_id` · `class_counts` (JSONB) · `person_count` ·
`density_level` · `fps` · `latency_ms` · `inference_ms`

This is the specification's `detections` table. It stores **per-second aggregates,
not per-object rows.** At 40 cameras × 10 FPS × 30 objects, a per-object table
accrues ~12,000 rows/second — a billion rows a day, to answer questions that are
all of the form "how many." We store the answer, not the raw material.

Partitioned by day; raw resolution retained 7 days, then rolled up.

### `zone_ticks` — 1 Hz per zone
`time` · `zone_id` · `occupancy_estimate` · `occupancy_confidence` ·
`anchor_age_s` · `class_counts` (JSONB) · `density_level`

`occupancy_confidence` and `anchor_age_s` exist because an occupancy figure with
no error bar is a liability in a crowd-safety product. See ADR 0006.

### `crossings` — event-driven
`time` · `camera_id` · `line_id` · `class` · `direction` (`in`|`out`)

**No `track_id` column.** The track that produced the crossing died inside the
worker, unpublished and unpersisted.

### `alerts`
`id` (uuid) · `time` · `type` · `severity` (`info`|`warning`|`critical`) ·
`camera_id` (nullable) · `zone_id` (nullable) · `title` · `description` ·
`snapshot_path` (nullable) · `status` (`open`|`acknowledged`|`resolved`|`suppressed`) ·
`assigned_operator_id` (nullable) · `acknowledged_at` · `resolved_at` ·
`dedup_key` · `context` (JSONB)

`dedup_key` = `(type, scope_key, cooldown_window)` and is **uniquely indexed**.
This is how at-least-once delivery from the event spine ([ADR 0007](../adr/0007-event-spine-and-aggregation-at-the-edge.md))
is made idempotent: a redelivered `rule.trigger` hits the unique constraint and
is absorbed. It generalizes the prototype's in-memory per-scope cooldown to a
system that survives a restart.

### `continuous aggregates` (materialized, refreshed on write)
`stats_minute`, `stats_hour`, `stats_day` — rollups of `camera_ticks` and
`crossings`. These serve every chart in the dashboard and every report. The
specification's `statistics` table is this, and it is derived, never written to
directly.

---

## Operations

### `audit_logs`
`id` · `time` · `actor_user_id` (nullable for system) · `action` · `resource_type` ·
`resource_id` · `ip` · `user_agent` · `before` (JSONB) · `after` (JSONB) · `result`

**Append-only.** Enforced in the database: `REVOKE UPDATE, DELETE` from the
application role, plus a `BEFORE UPDATE OR DELETE` trigger that raises. An
attacker with application-level credentials — including the `admin` role — cannot
erase their trail. This is the difference between an audit log and a log.

Every mutation of `cameras`, `zones`, `users`, `roles`, `settings`, every alert
acknowledgement, every login and logout, and **every access to a snapshot image**
writes here.

### `logs`
Application logs are **not** a database table. They are structured JSON to stdout,
shipped to Loki/OpenSearch. A `logs` table in PostgreSQL competes for write IOPS
with the telemetry that pays for the database. The specification's `logs` entry
is satisfied by the observability stack, and `audit_logs` — which has genuinely
different durability and immutability requirements — stays in PostgreSQL.

### `events`
The specification's `events` table is served by `crossings` plus the alert
lifecycle in `alerts`. There is no separate raw-event table; the durable event
record is the Redis stream (bounded) plus these two (permanent).

---

## Retention and erasure

| Data | Retention | Rationale |
|---|---|---|
| Raw `camera_ticks` / `zone_ticks` | 7 days | rolled into continuous aggregates |
| `stats_minute` | 90 days | operational reporting |
| `stats_hour` / `stats_day` | 5 years | trend analysis, no personal data |
| `crossings` | 90 days | anonymous counts |
| `alerts` | 1 year | incident record |
| Alert **snapshots** (images) | **30 days, configurable** | the only imagery of people the system stores; shortest defensible retention |
| `audit_logs` | 7 years, immutable | accreditation requirement |

Snapshots are the only personal-data-adjacent artifact in the system. Their
retention is short, their access is audited, and their deletion is automatic.
There is no subject-access-request machinery because there is no subject: nothing
in the system associates an image with a person's identity.
