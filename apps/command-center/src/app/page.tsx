import { StatusBadge } from "@/components/StatusBadge";
import { fetchApiHealth, type ApiHealth } from "@/lib/health";

// Health is never cached. A stale readiness figure that still looks live is the
// most dangerous single pixel this platform can draw (Operational SRS DSH-006).
export const dynamic = "force-dynamic";
export const revalidate = 0;

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8000";

function Panel({
  title,
  children,
}: {
  readonly title: string;
  readonly children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-surface-border bg-surface-raised p-5">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-content-faint">
        {title}
      </h2>
      {children}
    </section>
  );
}

function DependencyTable({ health }: { readonly health: ApiHealth }) {
  if (health.kind === "unknown") {
    return (
      <p className="font-mono text-sm text-content-muted">
        The control plane did not answer: {health.reason}. Its dependencies are{" "}
        <span className="text-state-unknown">unknown</span> — not healthy.
      </p>
    );
  }

  const entries = Object.entries(health.report.checks);
  if (entries.length === 0) {
    return <p className="font-mono text-sm text-content-muted">No dependencies registered.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left font-mono text-sm">
        <thead>
          <tr className="text-content-faint">
            <th className="pb-2 pr-6 font-medium">Dependency</th>
            <th className="pb-2 pr-6 font-medium">State</th>
            <th className="pb-2 pr-6 font-medium">Critical</th>
            <th className="pb-2 font-medium">Latency</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, check]) => (
            <tr key={name} className="border-t border-surface-border">
              <td className="py-2 pr-6 text-content">{name}</td>
              <td className="py-2 pr-6">
                <StatusBadge state={check.status} />
                {check.detail ? (
                  <span className="ml-2 text-content-faint">{check.detail}</span>
                ) : null}
              </td>
              <td className="py-2 pr-6 text-content-muted">{check.critical ? "yes" : "no"}</td>
              <td className="py-2 text-content-muted">{check.duration_ms.toFixed(1)} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function CommandCenterPage() {
  const health = await fetchApiHealth(CORE_API_URL);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-10 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">MANSOUR Vision</h1>
          <p className="mt-1 text-sm text-content-muted">
            Event Command &amp; Control Platform — Tomorrow Systems
          </p>
        </div>
        <StatusBadge state={health.kind} />
      </header>

      <div className="space-y-6">
        <Panel title="Control plane">
          <DependencyTable health={health} />
        </Panel>

        <Panel title="Privacy posture">
          <p className="text-sm leading-relaxed text-content-muted">
            This platform performs{" "}
            <strong className="text-content">anonymous operational monitoring only</strong>. It does
            not implement, and is architecturally incapable of, face recognition, person
            identification, biometric categorisation, identity tracking, cross-camera
            re-identification, or licence plate recognition.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-content-faint">
            Track identifiers are ephemeral, per-process, and never persisted or published. The
            guarantee is enforced by the system&apos;s structure, not by a policy document. See ADR
            0004.
          </p>
        </Panel>

        <Panel title="Milestone">
          <p className="text-sm leading-relaxed text-content-muted">
            Milestone 2 — the monorepo, the service shells, and the event contract. Camera
            management, zones, and live telemetry arrive in Milestone 3. Nothing on this screen is
            simulated: the control plane above is really being probed.
          </p>
        </Panel>
      </div>
    </main>
  );
}
