import { Reveal } from './Reveal'

const TIERS = [
  {
    name: 'CI-only',
    tagline: 'Connect repos',
    unlocks: ['Deploy timeline from workflow runs', 'Lead time & deploy frequency', 'Safety score on risky changes'],
  },
  {
    name: 'CI + CD',
    tagline: 'Connect repos + ArgoCD',
    unlocks: ['Full correlation: commit → sync → rollout', 'Change failure rate & MTTR', 'Sync status per service'],
  },
  {
    name: 'Full stack',
    tagline: 'Connect repos + cluster',
    unlocks: ['Post-deploy health scoring', 'Blast radius & dependency graph', 'Live alerts on degraded releases'],
  },
]

export function IntegrationTiers() {
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
            <div className="flex h-full flex-col rounded-lg border border-border bg-surface p-6">
              <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
                {tier.tagline}
              </span>
              <h3 className="mt-1 font-heading text-lg font-medium text-text">{tier.name}</h3>
              <ul className="mt-4 space-y-2 text-sm text-text-muted">
                {tier.unlocks.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-accent" aria-hidden="true">
                      +
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
