import { Link, useSearchParams } from 'react-router-dom'
import { Logo } from '../components/layout/Logo'
import { safeRedirectPath } from '../lib/safeRedirect'

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.5 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.46-1.19-1.11-1.51-1.11-1.51-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 2.5-.35c.85 0 1.7.12 2.5.35 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .28.18.61.69.5A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  )
}

export function Login() {
  const [searchParams] = useSearchParams()
  const redirect = safeRedirectPath(searchParams.get('redirect'))
  const githubHref = `/auth/github?redirect=${encodeURIComponent(redirect)}`

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden bg-background px-4">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[420px] bg-[radial-gradient(55%_100%_at_50%_0%,rgba(0,255,127,0.10),transparent_70%)]"
      />
      <div className="relative w-full max-w-sm rounded-xl border border-border bg-surface-raised p-8 text-center shadow-raised">
        <Logo className="justify-center" markClassName="h-9 w-9" />
        <p className="mt-4 text-sm leading-relaxed text-text-muted">
          Deployment-aware observability, in one place.
        </p>
        <a
          href={githubHref}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-md border border-border-strong bg-surface px-4 py-2.5 text-sm font-semibold text-text transition-colors hover:border-accent hover:text-accent"
        >
          <GitHubIcon />
          Sign in with GitHub
        </a>
        <p className="mt-4 text-xs text-text-faint">
          KubeX only requests the access it needs to read your workflow runs.
        </p>
      </div>
      <Link
        to="/"
        className="relative mt-6 text-sm text-text-muted transition-colors hover:text-text"
      >
        Back to home
      </Link>
    </div>
  )
}
