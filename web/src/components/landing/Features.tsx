import { Reveal } from './Reveal'

const FEATURES = [
  {
    title: 'Health scoring',
    body: 'Every deployment is scored 0–100 from error rate, latency, and restart deltas against its own baseline — automatically, no thresholds to tune.',
  },
  {
    title: 'DORA metrics',
    body: 'Deploy frequency, lead time, change failure rate, and MTTR, computed per-org and trended over time.',
  },
  {
    title: 'AI chat',
    body: 'Ask "why did payments degrade this morning?" in plain English and get an answer grounded in your actual deployment and metrics history.',
  },
  {
    title: 'Blast radius',
    body: 'See which downstream services depend on the one that just shipped, before an incident makes the dependency graph obvious.',
  },
  {
    title: 'Alerts',
    body: 'Degraded and failed deployments page your team in Slack the moment scoring completes — not after someone notices in prod.',
  },
  {
    title: 'Safety scores',
    body: 'A pre-deploy risk score from change size, timing, and recent history flags risky releases before they ship.',
  },
]

export function Features() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <Reveal>
        <h2 className="font-heading text-2xl font-semibold text-text sm:text-3xl">
          Everything you need to trust a deploy
        </h2>
      </Reveal>
      <div className="mt-12 grid grid-cols-1 gap-x-8 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delayMs={(i % 3) * 100}>
            <div className="border-l-2 border-border pl-4 transition-colors hover:border-accent">
              <h3 className="font-heading text-base font-medium text-text">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">{f.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
