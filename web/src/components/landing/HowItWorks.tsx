import { Reveal } from './Reveal'

const STEPS = [
  {
    step: '01',
    title: 'Connect repos',
    body: 'Install the GitHub App on your org. Webhooks for every workflow run are provisioned automatically — no manual secrets to copy.',
  },
  {
    step: '02',
    title: 'Connect cluster',
    body: 'Drop the lightweight cluster agent into your Kubernetes cluster. It reports deploy events and pod health back over an outbound connection.',
  },
  {
    step: '03',
    title: 'Observe and score',
    body: 'Every deployment gets a health score, a DORA trend, and an alert if it made things worse — before your team notices in prod.',
  },
]

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
      <Reveal>
        <h2 className="font-heading text-2xl font-semibold text-text sm:text-3xl">How it works</h2>
      </Reveal>
      <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-6">
        {STEPS.map((s, i) => (
          <Reveal key={s.step} delayMs={i * 120}>
            <div className="border-t border-border pt-5">
              <span className="font-heading text-sm text-text-muted">{s.step}</span>
              <h3 className="mt-2 font-heading text-lg font-medium text-text">{s.title}</h3>
              <p className="mt-2 text-sm text-text-muted">{s.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
