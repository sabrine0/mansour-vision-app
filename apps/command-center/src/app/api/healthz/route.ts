import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Liveness for the dashboard container.
 *
 * Deliberately probes nothing. If this endpoint depended on `core-api`, an API
 * outage would make the orchestrator kill every dashboard replica — converting a
 * recoverable dependency failure into a total one. The dashboard's job during an
 * API outage is to stay up and say the API is down.
 */
export function GET() {
  return NextResponse.json({ status: "ok", service: "command-center" });
}
