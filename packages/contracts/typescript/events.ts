/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Source: packages/contracts/schema/spine.schema.json
 * Regenerate: npm run contracts:generate
 *
 * The event contract for the MANSOUR Vision spine (ADR 0007).
 *
 * Note what is absent, and deliberately so: no track identifier, no person
 * identifier, no embedding, no biometric attribute. A crossing is decided from a
 * track's centroid history inside the worker; the track dies there and is never
 * published (ADR 0004).
 */

/* eslint-disable */

/**
 * Every event carried on the MANSOUR Vision event spine (ADR 0007). No event carries a track identifier, a person identifier, an embedding, or any biometric attribute (ADR 0004).
 */
export type SpineEvent = CameraTick | ZoneTick | CrossingEvent | CameraHealth | RuleTrigger;
/**
 * Fruin Level-of-Service bands (Detection SRS §4.1).
 *
 * `UNCALIBRATED` is not a band. It is the assertion that this camera cannot
 * express density in persons/m² and therefore has no opinion. It must never be
 * rendered as a colour, and it must never satisfy a crush-risk rule. A number
 * that looks authoritative and means nothing is the prohibited failure mode.
 */
export type DensityLevel = "uncalibrated" | "normal" | "elevated" | "high" | "critical";
/**
 * What the detector may emit.
 *
 * Exactly the pretrained COCO classes named in ADR 0003. Everything else the
 * specification asks for is either a configured zone polygon, or a rule over
 * these, or a deferred custom-model item. Adding a member here without a model
 * that produces it would be a lie in the type system.
 */
export type DetectionClass = "person" | "horse" | "dog" | "car" | "truck" | "bus" | "motorcycle" | "bicycle";
/**
 * Line-crossing polarity. Declared per line, never inferred from endpoint order.
 */
export type Direction = "in" | "out";
/**
 * Observed camera state.
 *
 * `UNKNOWN` exists because `HRS-007` requires that the absence of an
 * observation never be reported as a good one. A camera whose state we cannot
 * establish is `UNKNOWN`, never `ONLINE`.
 */
export type CameraState = "unknown" | "online" | "degraded" | "offline" | "tampered" | "maintenance";
/**
 * Alert severity (Operational SRS §10).
 *
 * `EMERGENCY` is never suppressed, never batched, never subject to quiet hours,
 * and never disarmed by a schedule. That is enforced downstream; the ordering
 * here is what makes it checkable.
 */
export type Severity = "info" | "warning" | "critical" | "emergency";

/**
 * Per-camera aggregate, 1 Hz. The specification's `detections`, summarised.
 */
export interface CameraTick {
  analytic_fps: number;
  camera_id: string;
  class_counts?: {
    [k: string]: number;
  };
  correlation_id?: string | null;
  density_level: DensityLevel;
  event_id: string;
  event_type?: "camera.tick";
  inference_ms: number;
  latency_ms: number;
  mean_confidence?: number | null;
  occurred_at: string;
  person_count: number;
  producer: string;
  schema_version?: number;
}
/**
 * Per-zone aggregate, 1 Hz.
 */
export interface ZoneTick {
  anchor_age_seconds: number;
  class_counts?: {
    [k: string]: number;
  };
  correlation_id?: string | null;
  density_level: DensityLevel;
  density_per_sqm?: number | null;
  event_id: string;
  event_type?: "zone.tick";
  occupancy_confidence: number;
  occupancy_estimate: number;
  occurred_at: string;
  producer: string;
  schema_version?: number;
  zone_id: string;
}
/**
 * A directional line crossing.
 *
 * Deliberately carries **no track identifier**. The track that produced this
 * crossing died inside the worker, unpublished and unpersisted (ADR 0004).
 *
 * Because there is no track id, the event's identity is its
 * `(line, class, direction, sequence)` — the worker supplies a monotonically
 * increasing per-line sequence number so that two people crossing the same line
 * in the same direction in the same second remain two events.
 */
export interface CrossingEvent {
  camera_id: string;
  correlation_id?: string | null;
  detection_class: DetectionClass;
  direction: Direction;
  event_id: string;
  event_type?: "crossing.event";
  line_id: string;
  occurred_at: string;
  producer: string;
  schema_version?: number;
  sequence: number;
  zone_id?: string | null;
}
/**
 * Camera health transition, plus a 10-second heartbeat.
 *
 * `last_frame_age_seconds` is the field that matters. Camera-offline is keyed
 * on frame staleness, not on whether the capture handle looks open: a dead
 * network stream leaves `read()` blocking for tens of seconds while the handle
 * still appears healthy.
 */
export interface CameraHealth {
  calibration_valid?: boolean;
  camera_id: string;
  correlation_id?: string | null;
  decode_errors?: number;
  event_id: string;
  event_type?: "camera.health";
  last_frame_age_seconds: number;
  occurred_at: string;
  producer: string;
  reconnect_count?: number;
  schema_version?: number;
  sequence: number;
  state: CameraState;
}
/**
 * A zone or line predicate was satisfied. Feeds `alert-engine`.
 *
 * This is not an alert. It is the observation from which the alert engine may
 * raise one, subject to cooldown, arming, and clustering. The distinction is
 * the reason the worker does not need to know about cooldowns at all.
 */
export interface RuleTrigger {
  camera_id?: string | null;
  config_version: number;
  context?: {
    [k: string]: number | string | boolean;
  };
  correlation_id?: string | null;
  dedup_key: string;
  event_id: string;
  event_type?: "rule.trigger";
  occurred_at: string;
  producer: string;
  rule: string;
  schema_version?: number;
  scope_key: string;
  severity: Severity;
  zone_id?: string | null;
}

/** Bumped when a field is removed or its meaning changes. */
export const SCHEMA_VERSION = 1;

/** Every event type carried on the spine. */
export const SPINE_EVENT_TYPES = ["camera.health","camera.tick","crossing.event","rule.trigger","zone.tick"] as const;

export type SpineEventType = (typeof SPINE_EVENT_TYPES)[number];
