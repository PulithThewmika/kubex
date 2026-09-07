import { Hero } from '../components/landing/Hero'
import { HowItWorks } from '../components/landing/HowItWorks'
import { Features } from '../components/landing/Features'
import { IntegrationTiers } from '../components/landing/IntegrationTiers'
import { LandingFooter } from '../components/landing/LandingFooter'

const GITHUB_HREF = '/auth/github?redirect=%2Fapp'

function LandingNav() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <span className="font-heading text-lg font-semibold tracking-wide text-text">KubeX</span>
        <a
          href={GITHUB_HREF}
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text transition-colors hover:bg-surface"
        >
          Sign in with GitHub
        </a>
      </div>
    </header>
  )
}

export function Landing() {
  return (
    <div className="min-h-dvh bg-background text-text">
      <LandingNav />
      <main>
        <Hero githubHref={GITHUB_HREF} />
        <HowItWorks />
        <Features />
        <IntegrationTiers />
      </main>
      <LandingFooter />
    </div>
  )
}
