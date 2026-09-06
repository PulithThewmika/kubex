import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, isError, refetch } = useAuth()
  const location = useLocation()

  if (isLoading) return null
  if (isError) {
    // A genuine backend failure (5xx) fetching /auth/me is not the same as
    // "unauthenticated" — redirecting to /login here would boot an
    // already-logged-in user over a transient outage. Offer a retry instead.
    return (
      <div className="flex h-dvh items-center justify-center bg-background px-4 text-center">
        <div>
          <p className="text-sm text-text-muted">Couldn't verify your session. Check your connection and try again.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }
  if (!isAuthenticated) {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }
  return <>{children}</>
}
