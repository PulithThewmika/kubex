import { Reveal } from '../components/landing/Reveal'
import { TornEdge } from '../components/landing/TornEdge'
import { MaxFeatures } from '../components/landing/MaxFeatures'
import { MaxIntegrations } from '../components/landing/MaxIntegrations'
import { MaxTiers } from '../components/landing/MaxTiers'

const GITHUB_HREF = '/auth/github?redirect=%2Fapp'
const SOURCE_HREF = 'https://github.com/PulithThewmika/kubex'

type Cta = { href: string; label: string }

const NAV_LINKS = [
  { label: 'Platform', href: '#platform' },
  { label: 'Integrations', href: '#integrations' },
  { label: 'How it works', href: '#how' },
]

function Nav({ cta }: { cta: Cta }) {
  return (
    <header className="sticky top-0 z-50 border-b-2 border-text bg-background">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:h-16 sm:px-6">
        <a href="#top" className="font-display text-2xl uppercase leading-none tracking-wide text-text sm:text-3xl">
          Kube<span className="text-accent">X</span>
        </a>
        <nav className="hidden gap-7 md:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="font-body text-xs font-bold uppercase tracking-[0.15em] text-text-muted transition-colors hover:text-accent"
            >
              {l.label}
            </a>
          ))}
        </nav>
        <a
          href={cta.href}
          className="border-2 border-accent bg-accent px-3 py-1.5 font-display text-sm uppercase tracking-wide text-background transition-colors hover:bg-background hover:text-accent sm:text-base"
        >
          {cta.label}
        </a>
      </div>
    </header>
  )
}

function DeployCard({
  className = '',
  rotate,
  label,
  verdict,
  score,
  tone,
}: {
  className?: string
  rotate: number
  label: string
  verdict: string
  score: string
  tone: 'healthy' | 'degraded'
}) {
  return (
    <div
      className={`w-56 border-2 border-text bg-background shadow-raised ${className}`}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      <div className="flex items-center justify-between bg-text px-3 py-1.5 font-mono text-[11px] font-bold uppercase text-background">
        <span>{label}</span>
        <span aria-hidden="true">●</span>
      </div>
      <div className="halftone px-3 py-4 text-accent">
        <p className="font-display text-4xl uppercase leading-none text-text">
          {verdict}
        </p>
        <p
          className={`mt-1 font-display text-6xl leading-none tabular-nums ${
            tone === 'healthy' ? 'text-accent' : 'text-outline text-text'
          }`}
        >
          {score}
        </p>
      </div>
    </div>
  )
}

function Hero({ cta }: { cta: Cta }) {
  return (
    <section id="top" className="relative overflow-hidden border-b-2 border-text bg-background">
      <div
        aria-hidden="true"
        className="absolute inset-0 text-accent/[0.08] halftone-lg"
      />
      <div className="relative mx-auto max-w-6xl px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16">
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem] lg:items-start">
          <Reveal>
            <h1 className="font-display uppercase text-accent">
              <span className="block text-[14vw] leading-[0.82] sm:text-[11vw] lg:text-[6.8rem]">
                Know if your
              </span>
              <span className="block text-[15vw] leading-[0.8] text-outline text-text sm:text-[12vw] lg:text-[8.5rem]">
                last deploy
              </span>
              <span className="block text-[14vw] leading-[0.82] sm:text-[11vw] lg:text-[6.8rem]">
                made it worse
              </span>
            </h1>
          </Reveal>
          <Reveal delayMs={120}>
            <p className="max-w-xs font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted lg:mt-4">
              KubeX correlates GitHub Actions, ArgoCD and Kubernetes runtime
              health into one deployment record — and scores every release
              automatically. No dashboards to babysit.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={cta.href}
                className="border-2 border-accent bg-accent px-5 py-2.5 font-display text-lg uppercase tracking-wide text-background transition-transform hover:-translate-y-1"
              >
                {cta.label} →
              </a>
              <a
                href={SOURCE_HREF}
                target="_blank"
                rel="noreferrer"
                className="border-2 border-text px-5 py-2.5 font-display text-lg uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
              >
                Source
              </a>
            </div>
          </Reveal>
        </div>

        {/* Scattered deployment cards */}
        <div className="mt-12 flex flex-wrap justify-center gap-6 lg:mt-4 lg:h-64 lg:justify-start">
          <DeployCard rotate={-5} label="orders #482" verdict="Healthy" score="94" tone="healthy" className="lg:relative lg:left-4 lg:top-2" />
          <DeployCard rotate={4} label="payments #517" verdict="Degraded" score="61" tone="degraded" className="lg:relative lg:-top-4 lg:left-10" />
          <DeployCard rotate={-2} label="frontend #903" verdict="Healthy" score="92" tone="healthy" className="hidden lg:relative lg:left-20 lg:top-6 lg:block" />
        </div>
      </div>

      {/* Integration ticker */}
      <div className="overflow-hidden border-t-2 border-text bg-accent py-2">
        <p className="whitespace-nowrap px-4 font-display text-xl uppercase tracking-wider text-background sm:text-2xl">
          GitHub Actions · ArgoCD · Kubernetes · Prometheus · Grafana · Slack · Loki · Alertmanager · DORA metrics · Health scoring ·
        </p>
      </div>
    </section>
  )
}

function Manifesto() {
  return (
    <section className="bg-background px-4 py-20 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-5xl text-center">
        <Reveal>
          <p className="font-display text-4xl uppercase leading-[0.95] text-text sm:text-6xl lg:text-7xl">
            We don't watch <span className="text-accent">dashboards.</span> We watch{' '}
            <span className="text-outline text-accent">deploys.</span> Every{' '}
            <span className="text-accent">commit</span>, every{' '}
            <span className="text-accent">sync</span>, every{' '}
            <span className="text-outline text-text">restart</span> — folded into one
            record and <span className="text-accent">scored</span> the moment it lands.
          </p>
        </Reveal>
      </div>
    </section>
  )
}

const STEPS = [
  { no: '01', title: 'Connect repos', body: 'Install the GitHub App on your org. Webhooks for every workflow run are provisioned automatically — no manual secrets to copy.' },
  { no: '02', title: 'Connect cluster', body: 'Drop the lightweight agent into your Kubernetes cluster. It reports deploy events and pod health over an outbound connection.' },
  { no: '03', title: 'Observe & score', body: 'Every deployment gets a health score, a DORA trend and an alert if it made things worse — before your team notices in prod.' },
]

function HowItWorks() {
  return (
    <section id="how" className="relative bg-text text-background">
      <TornEdge tone="text" className="-mt-4 sm:-mt-8" />
      <div className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6">
        <Reveal>
          <h2 className="font-display text-6xl uppercase leading-[0.82] text-accent sm:text-8xl lg:text-9xl">
            How it works
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-px border-2 border-background bg-background sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.no} delayMs={i * 110}>
              <div className="flex h-full flex-col bg-text p-6">
                <span className="font-display text-7xl leading-none tabular-nums text-accent">{s.no}</span>
                <h3 className="mt-3 font-display text-3xl uppercase leading-none text-background">{s.title}</h3>
                <p className="mt-3 font-body text-sm leading-relaxed text-background/70">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

function FinalCta({ cta }: { cta: Cta }) {
  return (
    <section className="relative bg-background">
      <TornEdge tone="background" className="-mt-4 sm:-mt-8" />
      <div className="mx-auto max-w-6xl px-4 py-24 text-center sm:px-6 sm:py-32">
        <Reveal>
          <h2 className="font-display text-6xl uppercase leading-[0.82] text-accent sm:text-8xl lg:text-[9rem]">
            Stop guessing.
            <br />
            <span className="text-outline text-text">Start shipping.</span>
          </h2>
          <div className="mt-10">
            <a
              href={cta.href}
              className="inline-block border-2 border-accent bg-accent px-10 py-5 font-display text-3xl uppercase tracking-wide text-background transition-transform hover:-translate-y-1"
            >
              {cta.label} →
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

const FOOTER_LINKS = [
  { label: 'GitHub', href: SOURCE_HREF },
  { label: 'Docs', href: 'https://github.com/PulithThewmika/kubex#readme' },
  { label: 'Project board', href: 'https://github.com/users/PulithThewmika/projects/3' },
]

function Footer() {
  return (
    <footer className="overflow-hidden border-t-2 border-text bg-background">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <p className="max-w-xs font-body text-xs font-bold uppercase tracking-[0.15em] text-text-faint">
            Deployment-aware observability. A solo build.
          </p>
          <nav className="flex gap-6">
            {FOOTER_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                target="_blank"
                rel="noreferrer"
                className="font-body text-xs font-bold uppercase tracking-[0.15em] text-text-muted transition-colors hover:text-accent"
              >
                {l.label}
              </a>
            ))}
          </nav>
        </div>
        <p className="mt-6 font-display text-[22vw] uppercase leading-[0.75] text-outline text-text/40">
          KubeX
        </p>
      </div>
    </footer>
  )
}

export function Landing({ isAuthenticated = false }: { isAuthenticated?: boolean }) {
  const cta: Cta = isAuthenticated
    ? { href: '/app', label: 'Go to dashboard' }
    : { href: GITHUB_HREF, label: 'Sign in with GitHub' }

  return (
    <div className="bg-background text-text">
      <Nav cta={cta} />
      <main>
        <Hero cta={cta} />
        <Manifesto />
        <MaxFeatures />
        <MaxIntegrations />
        <MaxTiers cta={cta} />
        <HowItWorks />
        <FinalCta cta={cta} />
      </main>
      <Footer />
    </div>
  )
}
