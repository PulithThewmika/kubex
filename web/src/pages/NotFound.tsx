import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="font-heading text-5xl font-semibold tabular-nums text-border-strong">404</p>
      <h1 className="font-heading text-xl font-semibold text-text">Page not found</h1>
      <p className="max-w-sm text-sm leading-relaxed text-text-muted">
        The page you're looking for doesn't exist or has moved.
      </p>
      <div className="mt-2 flex gap-2">
        <Link
          to="/app"
          className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-semibold text-background transition-colors hover:bg-accent-hover active:translate-y-px"
        >
          Back to dashboard
        </Link>
        <Link
          to="/"
          className="rounded-md border border-border-strong px-3.5 py-1.5 text-sm font-medium text-text transition-colors hover:border-accent hover:text-accent"
        >
          Home
        </Link>
      </div>
    </div>
  )
}
