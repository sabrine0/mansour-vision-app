-- Extensions required by the data model. Run once, at database initialisation.
--
-- TimescaleDB: `camera_ticks` and `zone_ticks` are hypertables, not tables. At
-- 40 cameras publishing 1 Hz aggregates they accrue tens of millions of rows per
-- event (docs/architecture/data-model.md).
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- PostGIS: zones carry a GPS boundary, and occupancy de-duplication across
-- overlapping camera coverage is computed from ground-plane geometry — never
-- from appearance matching, which would be re-identification (ADR 0004, 0006).
CREATE EXTENSION IF NOT EXISTS postgis;

-- Case-insensitive text, for user email addresses.
CREATE EXTENSION IF NOT EXISTS citext;

-- pgcrypto: `gen_random_uuid()` for server-side identifier defaults.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
