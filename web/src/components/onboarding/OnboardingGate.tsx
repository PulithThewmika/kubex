import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useClusters } from '../../hooks/useClusters'
import { useInstallations } from '../../hooks/useInstallations'

// Redirects a brand-new org to the setup wizard: shown only when the org
// hasn't completed onboarding AND has no GitHub App installations AND no
// connected clusters.
//
// The onboarding_completed flag is the fast path — V028 backfills it to true
// for every pre-existing org, so the common login never waits on (or is
// gated by) the installations/clusters queries. Only a genuinely new org
// (flag false) falls through to the connection checks.
export function OnboardingGate({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const installations = useInstallations()
  const clusters = useClusters()

  if (!user || user.onboarding_completed) return <>{children}</>

  // New org: wait for the connection checks before deciding. Don't render
  // the dashboard meanwhile (it would fire its own queries and flash before
  // the redirect), and don't trap the user in the wizard on a transient
  // query error — fail open to the dashboard.
  if (installations.isLoading || clusters.isLoading) return null
  if (installations.isError || clusters.isError) return <>{children}</>

  const nothingConnected =
    (installations.data?.length ?? 0) === 0 && (clusters.data?.length ?? 0) === 0
  if (nothingConnected) return <Navigate to="/app/onboarding" replace />
  return <>{children}</>
}
