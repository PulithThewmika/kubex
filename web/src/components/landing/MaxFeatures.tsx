import { Reveal } from './Reveal'
import { TornEdge } from './TornEdge'

const FEATURES = [
  { no: '01', title: 'Health scoring', body: 'Every deployment scored 0–100 from error rate, latency and restart deltas against its own baseline. No thresholds to tune.' },
  { no: '02', title: 'DORA metrics', body: 'Deploy frequency, lead time, change failure rate and MTTR — computed per-org in SQL and trended over time.' },
  { no: '03', title: 'AI chat', body: 'Ask "why did payments degrade this morning?" and get an answer grounded in your real deployment and metrics history.' },
  { no: '04', title: 'Blast radius', body: 'See which downstream services depend on the one that just shipped — before an incident makes the graph obvious.' },
  { no: '05', title: 'Slack alerts', body: 'Degraded and failed deployments page your team the moment scoring completes — not after someone notices in prod.' },
  { no: '06', title: 'Safety scores', body: 'A pre-deploy risk score from change size, timing and recent history flags risky releases before they ship.' },
]

export function MaxFeatures() {
  return (
    <section id="platform" className="relative bg-text pb-20 text-background sm:pb-28">
      <TornEdge tone="text" className="-mt-4 sm:-mt-8" />
      <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6">
        <Reveal>
          <h2 className="font-display text-6xl uppercase leading-[0.82] text-accent sm:text-8xl lg:text-[8.5rem]">
            Deployment-aware
          </h2>
        </Reveal>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.no} delayMs={(i % 3) * 90}>
              <article
                className="flex h-full flex-col border-2 border-background bg-text"
                style={{ transform: `rotate(${(i % 2 === 0 ? -1 : 1) * 1.2}deg)` }}
              >
                <div className="flex items-center justify-between bg-background px-4 py-2 text-accent halftone">
                  <span className="font-display text-lg uppercase tracking-wider text-accent">KUBEX</span>
                  <span className="font-display text-lg tabular-nums text-text">#{f.no}</span>
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <h3 className="font-display text-3xl uppercase leading-[0.9] text-background">{f.title}</h3>
                  <p className="mt-3 font-body text-sm leading-relaxed text-background/70">{f.body}</p>
                </div>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal>
          <h2 className="mt-12 text-right font-display text-5xl uppercase leading-[0.82] text-outline text-accent sm:text-8xl lg:text-[8.5rem]">
            by design
          </h2>
        </Reveal>
      </div>
    </section>
  )
}
