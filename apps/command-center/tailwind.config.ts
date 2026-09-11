import type { Config } from "tailwindcss";

/**
 * The command-center palette.
 *
 * Severity is never carried by colour alone (NFR-14): every severity has a
 * label and a shape as well as a hue. Operators with colour-vision deficiency
 * work in these rooms, and the video wall may be monochrome.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0b0f14",
          raised: "#111823",
          overlay: "#18212e",
          border: "#243044",
        },
        content: {
          DEFAULT: "#e6edf5",
          muted: "#8fa3bd",
          faint: "#5b6b83",
        },
        severity: {
          info: "#3b82f6",
          warning: "#f59e0b",
          critical: "#f97316",
          emergency: "#ef4444",
        },
        // Fruin Level-of-Service bands. `uncalibrated` is deliberately a neutral
        // grey and never a band colour: a camera without a homography has no
        // opinion about density, and rendering it as green would be a lie.
        density: {
          uncalibrated: "#5b6b83",
          normal: "#22c55e",
          elevated: "#eab308",
          high: "#f97316",
          critical: "#dc2626",
        },
        state: {
          online: "#22c55e",
          degraded: "#eab308",
          offline: "#ef4444",
          unknown: "#5b6b83",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
