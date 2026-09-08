import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { Reveal } from '../components/landing/Reveal'
import { Ticker } from '../components/landing/Ticker'
import { safeRedirectPath } from '../lib/safeRedirect'

function GitHubIcon({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.5 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.46-1.19-1.11-1.51-1.11-1.51-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 2.5-.35c.85 0 1.7.12 2.5.35 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .28.18.61.69.5A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  )
}

const POINTS = [
  'Read-only on your workflow runs — nothing else.',
  'Webhooks provisioned automatically. No secrets to copy.',
  'Session lives in an httpOnly cookie. Sign out any time.',
]

export function Login() {
  const [searchParams] = useSearchParams()
  const redirect = safeRedirectPath(searchParams.get('redirect'))
  const githubHref = `/auth/github?redirect=${encodeURIComponent(redirect)}`

  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden bg-background text-text">
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.07] halftone-lg" />

      <header className="relative z-10 border-b-2 border-text bg-text text-background">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6 sm:h-20">
          <Link to="/" className="shrink-0 transition-transform duration-300 hover:scale-[1.02] motion-reduce:transform-none">
            <img src="/header-logo.png" alt="KubeX Platform" className="h-11 w-auto select-none sm:h-14" />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-body text-xs font-bold uppercase tracking-[0.15em] text-background/60 transition-colors hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
        </div>
      </header>

      <main className="relative z-10 flex flex-1 items-center px-6 py-16 sm:px-10">
        <Reveal className="mx-auto w-full max-w-2xl">
          <p className="font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">Get started</p>
          <h1 className="mt-3 font-display text-6xl uppercase leading-[0.82] text-text sm:text-8xl">
            Sign <span className="text-accent">in.</span>
          </h1>
          <p className="mt-6 max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
            One click with GitHub. KubeX installs its app on your org and wires
            up every repo — you're scoring deployments in minutes.
          </p>

          <a
            href={githubHref}
            className="group mt-9 inline-flex items-center gap-3 border-2 border-accent bg-accent px-7 py-4 font-display text-xl uppercase tracking-wide text-background transition-transform duration-300 hover:-translate-y-1 active:translate-y-0 active:scale-[0.98] motion-reduce:transform-none sm:text-2xl"
          >
            <GitHubIcon className="h-6 w-6 sm:h-7 sm:w-7" />
            Sign in with GitHub
            <ArrowRight className="h-6 w-6 transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transform-none" />
          </a>

          <ul className="mt-10 space-y-3 border-t-2 border-text pt-6 font-body text-sm">
            {POINTS.map((point) => (
              <li key={point} className="flex gap-3 text-text-muted">
                <span aria-hidden="true" className="font-display text-lg leading-none text-accent">
                  +
                </span>
                <span className="leading-snug">{point}</span>
              </li>
            ))}
          </ul>
        </Reveal>
      </main>

      <div className="relative z-10">
        <Ticker />
      </div>
    </div>
  )
}
