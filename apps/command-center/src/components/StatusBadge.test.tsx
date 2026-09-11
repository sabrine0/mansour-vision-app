import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge, type BadgeState } from "./StatusBadge";

const STATES: BadgeState[] = ["ok", "degraded", "failed", "unknown"];

describe("StatusBadge", () => {
  it.each(STATES)("renders a text label for %s", (state) => {
    render(<StatusBadge state={state} />);
    expect(screen.getByRole("status")).toHaveTextContent(state.toUpperCase());
  });

  it("never conveys state by colour alone", () => {
    // NFR-14. A red dot indistinguishable from a green dot in greyscale is a
    // safety defect. Every state must carry a word and a distinct glyph.
    const glyphs = new Set<string>();
    const labels = new Set<string>();

    for (const state of STATES) {
      const { unmount } = render(<StatusBadge state={state} />);
      const text = screen.getByRole("status").textContent ?? "";
      glyphs.add(text.trim().charAt(0));
      labels.add(text.replace(/^\S\s*/, "").trim());
      unmount();
    }

    expect(glyphs.size).toBe(STATES.length);
    expect(labels.size).toBe(STATES.length);
  });

  it("hides the decorative glyph from assistive technology", () => {
    const { container } = render(<StatusBadge state="failed" />);
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});
