/**
 * Reading the platform's health, honestly.
 *
 * The rule this module exists to enforce is Volume II §2.7 and §15.5: when a
 * value cannot be established, it is reported as unknown. It is never rendered
 * as a plausible-looking default. The prohibited failure mode is a number that
 * looks authoritative and means nothing.
 */

export type CheckStatus = "ok" | "degraded" | "failed";

export interface CheckResult {
  readonly status: CheckStatus;
  readonly critical: boolean;
  readonly duration_ms: number;
  readonly detail?: string;
}

export interface ReadinessReport {
  readonly status: CheckStatus;
  readonly checks: Readonly<Record<string, CheckResult>>;
}

/** What the UI knows about the API. `unknown` is a first-class outcome. */
export type ApiHealth =
  | { readonly kind: "ok"; readonly report: ReadinessReport }
  | { readonly kind: "degraded"; readonly report: ReadinessReport }
  | { readonly kind: "failed"; readonly report: ReadinessReport }
  | { readonly kind: "unknown"; readonly reason: string };

const DEFAULT_TIMEOUT_MS = 3000;

function isCheckStatus(value: unknown): value is CheckStatus {
  return value === "ok" || value === "degraded" || value === "failed";
}

/**
 * Narrow an untrusted response body to a `ReadinessReport`.
 *
 * A malformed body is not coerced into a healthy-looking report. It is rejected,
 * and the caller renders `unknown`.
 */
export function parseReadiness(body: unknown): ReadinessReport | null {
  if (typeof body !== "object" || body === null) return null;

  const candidate = body as { status?: unknown; checks?: unknown };
  if (!isCheckStatus(candidate.status)) return null;
  if (typeof candidate.checks !== "object" || candidate.checks === null) return null;

  const checks: Record<string, CheckResult> = {};
  for (const [name, raw] of Object.entries(candidate.checks)) {
    if (typeof raw !== "object" || raw === null) return null;
    const check = raw as {
      status?: unknown;
      critical?: unknown;
      duration_ms?: unknown;
      detail?: unknown;
    };
    if (!isCheckStatus(check.status)) return null;
    if (typeof check.critical !== "boolean") return null;
    if (typeof check.duration_ms !== "number") return null;

    checks[name] = {
      status: check.status,
      critical: check.critical,
      duration_ms: check.duration_ms,
      ...(typeof check.detail === "string" ? { detail: check.detail } : {}),
    };
  }

  return { status: candidate.status, checks };
}

/**
 * Fetch `core-api`'s readiness.
 *
 * A 503 is not an error: it is the API correctly reporting that a critical
 * dependency is down, and its body carries which one. Only a transport failure,
 * a timeout, or an unparseable body yields `unknown`.
 */
export async function fetchApiHealth(
  baseUrl: string,
  {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    fetchImpl = fetch,
  }: {
    timeoutMs?: number;
    fetchImpl?: typeof fetch;
  } = {},
): Promise<ApiHealth> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(`${baseUrl}/readyz`, {
      signal: controller.signal,
      cache: "no-store",
    });

    const body: unknown = await response.json();
    const report = parseReadiness(body);
    if (report === null) {
      return { kind: "unknown", reason: "malformed readiness response" };
    }

    return { kind: report.status, report };
  } catch (error) {
    const reason =
      error instanceof DOMException && error.name === "AbortError"
        ? `no response within ${timeoutMs}ms`
        : error instanceof Error
          ? error.message
          : "unreachable";
    return { kind: "unknown", reason };
  } finally {
    clearTimeout(timer);
  }
}
