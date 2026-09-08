import { Reveal } from './Reveal'

type Cta = { href: string; label: string }

const TIERS = [
  {
    name: 'CI-only',
    tagline: 'Connect repos',
    featured: false,
    unlocks: ['Deploy timeline from workflow runs', 'Lead time & deploy frequency', 'Safety score on risky changes'],
  },
  {
    name: 'CI + CD',
    tagline: 'Connect repos + ArgoCD',
    featured: false,
    unlocks: ['Full correlation: commit to sync to rollout', 'Change failure rate & MTTR', 'Sync status per service'],
  },
  {
    name: 'Full stack',
    tagline: 'Connect repos + cluster',
    featured: true,
    unlocks: ['Post-deploy health scoring', 'Blast radius & dependency graph', 'Live alerts on degraded releases'],
  },
]

export function IntegrationTiers({ cta }: { cta: Cta }) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <Reveal>
        <h2 className="font-heading text-2xl font-semibold text-text sm:text-3xl">
          Start where you are, unlock as you connect more
        </h2>
      </Reveal>
      <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
        {TIERS.map((tier, i) => (
          <Reveal key={tier.name} delayMs={i * 120}>
            <div
              className={`flex h-full flex-col rounded-xl border bg-surface p-6 ${
                tier.featured ? 'border-accent/60 shadow-card' : 'border-border'
              }`}
            >
              <span className="text-xs font-medium uppercase tracking-wide text-text-faint">
                {tier.tagline}
              </span>
              <h3 className="mt-1 font-heading text-lg font-medium text-text">{tier.name}</h3>
              <ul className="mt-4 space-y-2.5 text-sm text-text-muted">
                {tier.unlocks.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-accent" aria-hidden="true">
                      +
                    </span>
                    <span className="leading-snug">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
      <Reveal>
        <div className="mt-12 flex justify-center">
          <a
            href={cta.href}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-hover active:translate-y-px"
          >
            {cta.label}
          </a>
        </div>
      </Reveal>
    </section>
  )
}
