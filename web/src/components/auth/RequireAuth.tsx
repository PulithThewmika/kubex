import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { AuthErrorState } from './AuthErrorState'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, isError, refetch } = useAuth()
  const location = useLocation()

  if (isLoading) return null
  if (isError) return <AuthErrorState onRetry={() => refetch()} />
  if (!isAuthenticated) {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }
  return <>{children}</>
}
