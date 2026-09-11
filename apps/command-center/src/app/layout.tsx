import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "MANSOUR Vision — Command Center",
  description:
    "AI-powered event command and control. Anonymous operational monitoring only: " +
    "no face recognition, no person identification, no biometric categorisation, " +
    "no re-identification, no licence plate recognition.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#0b0f14",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" dir="ltr">
      {/* `lang` and `dir` become dynamic in Phase 3: the operators are Moroccan,
          and an English-only console staffed under stress by French- and
          Arabic-speaking officers is a safety hazard (Operational SRS ADM-007). */}
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
