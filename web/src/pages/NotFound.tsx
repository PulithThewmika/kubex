import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="font-heading text-4xl font-semibold text-text-muted">404</p>
      <h1 className="font-heading text-xl font-semibold text-text">Page not found</h1>
      <p className="max-w-sm text-sm text-text-muted">
        The page you're looking for doesn't exist or has moved.
      </p>
      <Link
        to="/app"
        className="mt-2 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-background transition-opacity hover:opacity-90"
      >
        Back to dashboard
      </Link>
    </div>
  )
}
