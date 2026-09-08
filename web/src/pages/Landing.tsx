import { CinematicFooter } from '@/components/ui/motion-footer'
import { Reveal } from '../components/landing/Reveal'
import { Ticker } from '../components/landing/Ticker'
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
    <header className="sticky top-0 z-50 border-b-2 border-background bg-text text-background">
      <div className="flex h-14 w-full items-center px-4 sm:h-16 sm:px-8 lg:px-12">
        <a href="#top" className="font-display text-2xl uppercase leading-none tracking-wide text-background sm:text-3xl">
          Kube<span className="text-accent">X</span>
        </a>
        <nav className="hidden flex-1 justify-center gap-9 md:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="font-body text-xs font-bold uppercase tracking-[0.15em] text-background/60 transition-colors hover:text-accent"
            >
              {l.label}
            </a>
          ))}
        </nav>
        <a
          href={cta.href}
          className="ml-auto border-2 border-background bg-accent px-3 py-1.5 font-display text-sm uppercase tracking-wide text-background transition-colors hover:bg-background hover:text-text sm:text-base"
        >
          {cta.label}
        </a>
      </div>
    </header>
  )
}

function Hero({ cta }: { cta: Cta }) {
  return (
    <section
      id="top"
      className="relative flex min-h-[calc(100dvh-3.5rem)] flex-col overflow-hidden border-b-2 border-text bg-background sm:min-h-[calc(100dvh-4rem)]"
    >
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.08] halftone-lg" />
      <div className="relative flex w-full flex-1 items-center px-6 pt-16 sm:px-10 sm:pt-20 lg:px-14">
        <Reveal className="w-full lg:max-w-[44%] xl:max-w-[40%]">
          <h1 className="font-display text-6xl uppercase leading-[0.82] text-text sm:text-8xl lg:text-8xl">
            <span className="block">Know if your</span>
            <span className="block">last deploy</span>
            <span className="block">made it worse</span>
          </h1>
          <p className="mt-8 max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
            KubeX correlates GitHub Actions, ArgoCD and Kubernetes runtime
            health into one deployment record — and scores every release
            automatically. No dashboards to babysit.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
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

        {/* Collage anchored to the bottom-right corner, its base meeting the
            marquee bar. Decorative — dropped on narrow screens. */}
        <img
          src="/hero-image.png"
          alt="An analyst scanning the horizon through binoculars, deployment charts rising behind"
          width={1080}
          height={1147}
          draggable={false}
          className="pointer-events-none absolute bottom-0 right-0 hidden w-[36rem] select-none lg:block xl:right-4 xl:w-[44rem] 2xl:w-[48rem]"
        />
      </div>

      <Ticker />
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
      <CinematicFooter cta={cta} />
    </div>
  )
}
