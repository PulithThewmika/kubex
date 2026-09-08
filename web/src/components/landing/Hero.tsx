import { HealthRing } from '../HealthRing'
import { Reveal } from './Reveal'

type Cta = { href: string; label: string }

// A compact, honest slice of the real product surface — the same HealthRing
// the app renders, over a few representative service rows. Not a screenshot,
// not a fake dashboard: real components, sample data.
function ProductPreview() {
  const rows = [
    { name: 'frontend', score: 92, verdict: 'healthy' as const },
    { name: 'orders', score: 94, verdict: 'healthy' as const },
    { name: 'payments', score: 61, verdict: 'degraded' as const },
  ]
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-raised">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <span className="font-mono text-xs text-text-muted">orders-api · deploy #482</span>
        <span className="rounded-full bg-healthy/10 px-2 py-0.5 text-xs font-medium text-healthy">
          healthy · 94
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        {[
          { label: 'Deploy freq', value: '4.2/day' },
          { label: 'Lead time', value: '38m' },
          { label: 'CFR 30d', value: '6.1%' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-lg border border-border p-3">
            <dt className="text-xs text-text-faint">{stat.label}</dt>
            <dd className="mt-1 font-heading text-lg tabular-nums text-text">{stat.value}</dd>
          </div>
        ))}
      </dl>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li key={row.name} className="flex items-center gap-3">
            <HealthRing score={row.score} verdict={row.verdict} size={32} />
            <span className="text-sm text-text">{row.name}</span>
            <span className="ml-auto font-mono text-xs text-text-muted">{row.verdict}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Hero({ cta }: { cta: Cta }) {
  return (
    <section className="mx-auto grid max-w-6xl grid-cols-1 gap-12 px-4 pb-20 pt-16 sm:px-6 sm:pb-28 sm:pt-24 lg:grid-cols-2 lg:items-center lg:gap-10">
      <Reveal>
        <h1 className="font-heading text-4xl font-semibold leading-[1.1] tracking-tight text-text sm:text-5xl">
          Know if your last deploy made things worse.
        </h1>
        <p className="mt-5 max-w-md text-base leading-relaxed text-text-muted sm:text-lg">
          KubeX correlates CI, CD, and Kubernetes runtime health into one deployment record and
          scores every release automatically. No dashboards to babysit.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-4">
          <a
            href={cta.href}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-hover active:translate-y-px"
          >
            {cta.label}
          </a>
          <a
            href="https://github.com/PulithThewmika/kubex"
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-text-muted transition-colors hover:text-text"
          >
            View the source
          </a>
        </div>
      </Reveal>
      <Reveal delayMs={150}>
        <ProductPreview />
      </Reveal>
    </section>
  )
}
