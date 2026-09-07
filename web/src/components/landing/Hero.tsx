import { Reveal } from './Reveal'

function DashboardMockup() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <span className="text-xs font-medium text-text-muted">orders-api · deploy #482</span>
        <span className="rounded-full bg-healthy/10 px-2 py-0.5 text-xs font-medium text-healthy">
          healthy · 94
        </span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {[
          { label: 'Deploy freq', value: '4.2/day' },
          { label: 'Lead time', value: '38m' },
          { label: 'CFR (30d)', value: '6%' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-md border border-border p-3">
            <p className="text-xs text-text-muted">{stat.label}</p>
            <p className="mt-1 font-heading text-lg text-text">{stat.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        {[
          { name: 'frontend', pct: 92, tone: 'bg-healthy' },
          { name: 'orders', pct: 94, tone: 'bg-healthy' },
          { name: 'payments', pct: 61, tone: 'bg-degraded' },
        ].map((row) => (
          <div key={row.name} className="flex items-center gap-3">
            <span className="w-16 shrink-0 text-xs text-text-muted">{row.name}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-background">
              <div className={`h-full rounded-full ${row.tone}`} style={{ width: `${row.pct}%` }} />
            </div>
            <span className="w-6 shrink-0 text-right text-xs text-text-muted">{row.pct}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Hero({ githubHref }: { githubHref: string }) {
  return (
    <section className="mx-auto grid max-w-6xl grid-cols-1 gap-12 px-4 py-20 sm:px-6 sm:py-28 lg:grid-cols-2 lg:items-center lg:gap-8">
      <Reveal>
        <h1 className="font-heading text-4xl font-semibold leading-tight tracking-tight text-text sm:text-5xl">
          Know if your last deploy made things worse.
        </h1>
        <p className="mt-5 max-w-md text-base text-text-muted sm:text-lg">
          KubeX correlates CI, CD, and Kubernetes runtime health into one deployment record and
          scores every release automatically — no dashboards to babysit.
        </p>
        <a
          href={githubHref}
          className="mt-8 inline-flex items-center gap-2 rounded-md bg-text px-5 py-2.5 text-sm font-medium text-background transition-colors hover:opacity-90"
        >
          Sign in with GitHub
        </a>
      </Reveal>
      <Reveal delayMs={150}>
        <DashboardMockup />
      </Reveal>
    </section>
  )
}
