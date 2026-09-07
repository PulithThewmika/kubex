import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useClusters } from '../../hooks/useClusters'
import { useInstallations } from '../../hooks/useInstallations'

// Redirects a freshly-onboarded org to the setup wizard: shown when the org
// hasn't completed onboarding AND has no GitHub App installations AND no
// connected clusters. Once any of those is true the app never auto-shows the
// wizard again (it stays reachable from Settings).
export function OnboardingGate({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { data: installations, isLoading: loadingInstalls } = useInstallations()
  const { data: clusters, isLoading: loadingClusters } = useClusters()

  // Don't gate on incomplete data — a slow API shouldn't bounce the user to
  // onboarding, nor briefly flash the dashboard before redirecting.
  if (!user || loadingInstalls || loadingClusters) return <>{children}</>

  const needsOnboarding =
    !user.onboarding_completed && (installations?.length ?? 0) === 0 && (clusters?.length ?? 0) === 0

  if (needsOnboarding) return <Navigate to="/app/onboarding" replace />
  return <>{children}</>
}
