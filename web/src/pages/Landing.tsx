import { Hero } from '../components/landing/Hero'
import { HowItWorks } from '../components/landing/HowItWorks'
import { Features } from '../components/landing/Features'
import { IntegrationTiers } from '../components/landing/IntegrationTiers'
import { LandingFooter } from '../components/landing/LandingFooter'
import { Logo } from '../components/layout/Logo'

const GITHUB_HREF = '/auth/github?redirect=%2Fapp'

type Cta = { href: string; label: string }

function LandingNav({ cta }: { cta: Cta }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo markClassName="h-7 w-7" />
        <a
          href={cta.href}
          className="rounded-md border border-border-strong px-3.5 py-1.5 text-sm font-medium text-text transition-colors hover:border-accent hover:text-accent"
        >
          {cta.label}
        </a>
      </div>
    </header>
  )
}

export function Landing({ isAuthenticated = false }: { isAuthenticated?: boolean }) {
  const cta: Cta = isAuthenticated
    ? { href: '/app', label: 'Go to dashboard' }
    : { href: GITHUB_HREF, label: 'Sign in with GitHub' }

  return (
    <div className="relative min-h-dvh overflow-hidden bg-background text-text">
      {/* Ambient accent wash behind the hero — one soft radial, not a mesh. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-[radial-gradient(60%_100%_at_50%_0%,rgba(249,115,22,0.10),transparent_70%)]"
      />
      <div className="relative">
        <LandingNav cta={cta} />
        <main>
          <Hero cta={cta} />
          <HowItWorks />
          <Features />
          <IntegrationTiers cta={cta} />
        </main>
        <LandingFooter />
      </div>
    </div>
  )
}
