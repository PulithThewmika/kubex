import { useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { CinematicFooter } from '@/components/ui/motion-footer'
import { DISTANCE, DURATION, EASE, prefersReducedMotion } from '@/lib/motion'
import { Reveal } from '../components/landing/Reveal'
import { Ticker } from '../components/landing/Ticker'
import { TornEdge } from '../components/landing/TornEdge'
import { MaxFeatures } from '../components/landing/MaxFeatures'
import { MaxIntegrations } from '../components/landing/MaxIntegrations'
import { MaxTiers } from '../components/landing/MaxTiers'

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger)
}

const HERO_LINES = ['Know if your', 'last deploy', 'made it worse']

const GITHUB_HREF = '/auth/github?redirect=%2Fapp'
const SOURCE_HREF = 'https://github.com/PulithThewmika/kubex'

type Cta = { href: string; label: string }

const NAV_LINKS = [
  { label: 'Platform', href: '#platform' },
  { label: 'Integrations', href: '#integrations' },
  { label: 'How it works', href: '#how' },
]

function Nav({ cta }: { cta: Cta }) {
  const innerRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!innerRef.current || prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      gsap.from(innerRef.current, {
        y: -14,
        autoAlpha: 0,
        duration: DURATION.base,
        ease: EASE.smooth,
        delay: 0.05,
      })
    }, innerRef)
    return () => ctx.revert()
  }, [])

  return (
    <header className="sticky top-0 z-50 border-b-2 border-background bg-text text-background">
      <div
        ref={innerRef}
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:h-20 sm:px-6 lg:px-4"
      >
        <a href="#top" className="shrink-0 transition-transform duration-300 hover:scale-[1.02] motion-reduce:transform-none">
          <img
            src="/header-logo.png"
            alt="KubeX Platform"
            className="h-12 w-auto select-none sm:h-16"
          />
        </a>
        <nav className="hidden gap-7 md:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="relative font-body text-xs font-bold uppercase tracking-[0.15em] text-background/60 transition-colors after:absolute after:-bottom-1.5 after:left-0 after:h-0.5 after:w-full after:origin-left after:scale-x-0 after:bg-accent after:transition-transform after:duration-300 hover:text-accent hover:after:scale-x-100 motion-reduce:after:transition-none"
            >
              {l.label}
            </a>
          ))}
        </nav>
        <a
          href={cta.href}
          className="border-2 border-background bg-accent px-4 py-2 font-display text-base uppercase tracking-wide text-background transition-all duration-300 hover:-translate-y-0.5 hover:bg-background hover:text-text active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none sm:text-lg"
        >
          {cta.label}
        </a>
      </div>
    </header>
  )
}

function Hero({ cta }: { cta: Cta }) {
  const sectionRef = useRef<HTMLElement>(null)
  const halftoneRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const paraRef = useRef<HTMLParagraphElement>(null)
  const ctaRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const tickerRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const scope = sectionRef.current
    if (!scope) return

    // Reduced motion: no entrance choreography, no parallax — content renders
    // at its natural state. (Respecting the OS "reduce motion" setting; turn
    // that off to see the full hero sequence.)
    if (prefersReducedMotion()) return

    const ctx = gsap.context(() => {
      // Entrance — one coordinated sequence: heading lines, copy, CTAs, then
      // the collage rising in, then the ticker.
      const lines = headingRef.current?.querySelectorAll('.hero-line')
      const tl = gsap.timeline({ defaults: { ease: EASE.smooth } })
      if (lines?.length) {
        tl.from(lines, {
          y: DISTANCE.md,
          autoAlpha: 0,
          duration: DURATION.slow,
          ease: EASE.premium,
          stagger: 0.09,
        })
      }
      tl.from(paraRef.current, { y: DISTANCE.sm, autoAlpha: 0, duration: DURATION.base }, '-=0.42')
        .from(
          ctaRef.current?.children ?? [],
          { y: DISTANCE.xs, autoAlpha: 0, duration: DURATION.base, stagger: 0.08 },
          '-=0.3',
        )
        .from(
          imgRef.current,
          {
            autoAlpha: 0,
            scale: 1.07,
            yPercent: 4,
            transformOrigin: 'bottom right',
            duration: DURATION.xslow,
            ease: EASE.soft,
          },
          '-=0.8',
        )
        .from(tickerRef.current, { y: DISTANCE.md, autoAlpha: 0, duration: DURATION.base }, '-=0.85')
    }, scope)

    // Depth on scroll-out — collage and texture drift at different rates.
    // Desktop only (the collage is hidden below lg).
    const mm = gsap.matchMedia()
    mm.add('(min-width: 1024px)', () => {
      const scrollTrigger = { trigger: scope, start: 'top top', end: 'bottom top', scrub: 0.5 }
      gsap.to(imgRef.current, { yPercent: -14, ease: 'none', scrollTrigger })
      gsap.to(halftoneRef.current, { yPercent: 12, ease: 'none', scrollTrigger })
    })

    return () => {
      ctx.revert()
      mm.revert()
    }
  }, [])

  return (
    <section
      ref={sectionRef}
      id="top"
      className="relative flex min-h-[calc(100dvh-4rem)] flex-col overflow-hidden border-b-2 border-text bg-background sm:min-h-[calc(100dvh-5rem)]"
    >
      <div
        ref={halftoneRef}
        aria-hidden="true"
        className="absolute inset-x-0 -inset-y-[10%] text-accent/[0.08] halftone-lg"
      />
      <div className="relative mx-auto flex w-full max-w-6xl flex-1 items-center px-4 pt-16 sm:px-6 sm:pt-20">
        <div className="w-full lg:max-w-[52%]">
          <h1
            ref={headingRef}
            className="font-display text-6xl uppercase leading-[0.82] text-text sm:text-8xl lg:text-8xl"
          >
            {HERO_LINES.map((line) => (
              <span key={line} className="hero-line block">
                {line}
              </span>
            ))}
          </h1>
          <p
            ref={paraRef}
            className="mt-10 max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted"
          >
            KubeX correlates GitHub Actions, ArgoCD and Kubernetes runtime
            health into one deployment record — and scores every release
            automatically. No dashboards to babysit.
          </p>
          <div ref={ctaRef} className="mt-7 flex flex-wrap gap-3">
            <a
              href={cta.href}
              className="group border-2 border-accent bg-accent px-5 py-2.5 font-display text-lg uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none"
            >
              {cta.label}{' '}
              <span className="ml-0.5 inline-block transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transform-none">
                →
              </span>
            </a>
            <a
              href={SOURCE_HREF}
              target="_blank"
              rel="noreferrer"
              className="border-2 border-text px-5 py-2.5 font-display text-lg uppercase tracking-wide text-text transition-all duration-300 hover:border-accent hover:text-accent active:scale-[0.98] motion-reduce:transform-none"
            >
              Source
            </a>
          </div>
        </div>

        {/* Collage anchored to the bottom-right corner, its base meeting the
            marquee bar. Decorative — dropped on narrow screens. */}
        <img
          ref={imgRef}
          src="/hero-image.png"
          alt="An analyst scanning the horizon through binoculars, deployment charts rising behind"
          width={1080}
          height={1147}
          draggable={false}
          className="pointer-events-none absolute bottom-0 right-2 hidden w-[34rem] select-none will-change-transform lg:block xl:right-4 xl:w-[42rem]"
        />
      </div>

      <div ref={tickerRef}>
        <Ticker />
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
