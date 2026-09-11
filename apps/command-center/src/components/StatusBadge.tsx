import type { CheckStatus } from "@/lib/health";

export type BadgeState = CheckStatus | "unknown";

/**
 * Severity and state are never carried by colour alone (NFR-14).
 *
 * Every badge pairs its hue with a glyph and a word. Operators with
 * colour-vision deficiency work in these rooms, and the video wall may be
 * monochrome. A red dot that reads identically to a green dot in greyscale is a
 * safety defect, not a styling preference.
 */
const PRESENTATION: Record<BadgeState, { label: string; glyph: string; className: string }> = {
  ok: {
    label: "OK",
    glyph: "●",
    className: "text-state-online border-state-online/40 bg-state-online/10",
  },
  degraded: {
    label: "DEGRADED",
    glyph: "▲",
    className: "text-state-degraded border-state-degraded/40 bg-state-degraded/10",
  },
  failed: {
    label: "FAILED",
    glyph: "■",
    className: "text-state-offline border-state-offline/40 bg-state-offline/10",
  },
  unknown: {
    label: "UNKNOWN",
    glyph: "?",
    className: "text-state-unknown border-state-unknown/40 bg-state-unknown/10",
  },
};

export function StatusBadge({ state }: { readonly state: BadgeState }) {
  const { label, glyph, className } = PRESENTATION[state];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-xs font-medium ${className}`}
      role="status"
    >
      <span aria-hidden="true">{glyph}</span>
      {label}
    </span>
  );
}
