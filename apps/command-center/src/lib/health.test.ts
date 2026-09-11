import { describe, expect, it, vi } from "vitest";

import { fetchApiHealth, parseReadiness } from "./health";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const OK_BODY = {
  status: "ok",
  checks: { postgres: { status: "ok", critical: true, duration_ms: 1.2 } },
};

describe("parseReadiness", () => {
  it("accepts a well-formed report", () => {
    expect(parseReadiness(OK_BODY)).toEqual(OK_BODY);
  });

  it("keeps the failure detail", () => {
    const report = parseReadiness({
      status: "failed",
      checks: {
        redis: { status: "failed", critical: true, duration_ms: 3, detail: "connection refused" },
      },
    });

    expect(report?.checks.redis?.detail).toBe("connection refused");
  });

  it.each([
    ["null", null],
    ["a string", "ok"],
    ["a missing status", { checks: {} }],
    ["an unknown status", { status: "fine", checks: {} }],
    ["missing checks", { status: "ok" }],
    [
      "a check without criticality",
      { status: "ok", checks: { db: { status: "ok", duration_ms: 1 } } },
    ],
    [
      "a check with a non-numeric duration",
      { status: "ok", checks: { db: { status: "ok", critical: true, duration_ms: "fast" } } },
    ],
  ])("rejects %s rather than coercing it", (_label, body) => {
    expect(parseReadiness(body)).toBeNull();
  });
});

describe("fetchApiHealth", () => {
  it("reports ok when every dependency is up", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(OK_BODY));

    const health = await fetchApiHealth("http://api", { fetchImpl });

    expect(health.kind).toBe("ok");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api/readyz",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("treats 503 as a valid report, not as an error", async () => {
    // A 503 is the API correctly saying a critical dependency is down, and its
    // body names which one. Discarding that would throw away the diagnosis.
    const body = {
      status: "failed",
      checks: { postgres: { status: "failed", critical: true, duration_ms: 5, detail: "refused" } },
    };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(body, 503));

    const health = await fetchApiHealth("http://api", { fetchImpl });

    expect(health.kind).toBe("failed");
    if (health.kind === "failed") {
      expect(health.report.checks.postgres?.detail).toBe("refused");
    }
  });

  it("reports degraded when a non-critical dependency is down", async () => {
    const body = {
      status: "degraded",
      checks: { metrics: { status: "failed", critical: false, duration_ms: 2 } },
    };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(body));

    expect((await fetchApiHealth("http://api", { fetchImpl })).kind).toBe("degraded");
  });

  it("reports unknown, never ok, when the API is unreachable", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));

    const health = await fetchApiHealth("http://api", { fetchImpl });

    expect(health.kind).toBe("unknown");
    if (health.kind === "unknown") expect(health.reason).toBe("ECONNREFUSED");
  });

  it("reports unknown when the body is malformed", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ status: "great" }));

    const health = await fetchApiHealth("http://api", { fetchImpl });

    expect(health.kind).toBe("unknown");
    if (health.kind === "unknown") expect(health.reason).toBe("malformed readiness response");
  });

  it("reports unknown on timeout rather than hanging the console", async () => {
    const fetchImpl = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );

    const health = await fetchApiHealth("http://api", { fetchImpl, timeoutMs: 10 });

    expect(health.kind).toBe("unknown");
    if (health.kind === "unknown") expect(health.reason).toContain("no response within 10ms");
  });
});
