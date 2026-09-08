import { Reveal } from './Reveal'
import { TornEdge } from './TornEdge'

type Cta = { href: string; label: string }

const TIERS = [
  {
    word: 'BASE',
    name: 'CI only',
    connect: 'Connect repos',
    featured: false,
    unlocks: ['Deploy timeline from workflow runs', 'Lead time & deploy frequency', 'Safety score on risky changes'],
  },
  {
    word: 'CORE',
    name: 'CI + CD',
    connect: 'Connect repos + ArgoCD',
    featured: true,
    unlocks: ['Full correlation: commit → sync → rollout', 'Change failure rate & MTTR', 'Sync status per service'],
  },
  {
    word: 'FULL',
    name: 'Full stack',
    connect: 'Connect repos + cluster',
    featured: false,
    unlocks: ['Post-deploy health scoring', 'Blast radius & dependency graph', 'Live alerts on degraded releases'],
  },
]

export function MaxTiers({ cta }: { cta: Cta }) {
  return (
    <section className="relative bg-accent text-background">
      <TornEdge tone="accent" className="-mt-4 sm:-mt-8" />
      <div className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6">
        <Reveal>
          <h2 className="font-display text-6xl uppercase leading-[0.82] sm:text-8xl lg:text-9xl">
            Pick your
            <br />
            <span className="text-outline text-background">integration tier</span>
          </h2>
          <p className="mt-6 max-w-lg font-body text-sm font-bold uppercase leading-relaxed tracking-wide text-background/80">
            Every tier is free — the "price" is how much of your stack you wire
            in. Start where you are, unlock as you connect more.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">
          {TIERS.map((tier, i) => (
            <Reveal key={tier.name} delayMs={i * 110}>
              <div
                className={`flex h-full flex-col border-2 border-background ${
                  tier.featured ? 'bg-background text-text' : 'bg-accent text-background'
                }`}
              >
                <div
                  className={`border-b-2 border-background px-5 py-3 ${
                    tier.featured ? 'bg-accent text-background' : 'bg-background text-accent'
                  }`}
                >
                  <span className="font-body text-[11px] font-bold uppercase tracking-[0.2em]">
                    {tier.connect}
                  </span>
                  <h3 className="font-display text-3xl uppercase leading-none">{tier.name}</h3>
                </div>
                <ul className="flex-1 space-y-3 px-5 py-6 font-body text-sm">
                  {tier.unlocks.map((u) => (
                    <li key={u} className="flex gap-2">
                      <span aria-hidden="true" className="font-display text-lg leading-none text-current">
                        +
                      </span>
                      <span className={tier.featured ? 'text-text-muted' : 'text-background/90'}>{u}</span>
                    </li>
                  ))}
                </ul>
                <div
                  className={`border-t-2 border-background px-5 py-3 font-display text-5xl uppercase leading-none ${
                    tier.featured ? 'text-accent' : 'text-background'
                  }`}
                >
                  {tier.word}
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal>
          <div className="mt-14">
            <a
              href={cta.href}
              className="inline-block border-2 border-background bg-background px-8 py-4 font-display text-2xl uppercase tracking-wide text-accent transition-transform hover:-translate-y-1"
            >
              {cta.label} →
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
