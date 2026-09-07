import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../contexts/AuthContext'
import { jsonResponse, makeCluster, makeInstallation, stubRoutedFetch } from '../../test/fixtures'
import { OnboardingGate } from './OnboardingGate'

const ME = {
  user_id: '1',
  login: 'octocat',
  email: null,
  avatar_url: null,
  org_id: '2',
  org_name: 'Acme',
  org_slug: 'acme',
  onboarding_completed: false,
}

function renderGate(routes: Record<string, () => Response>) {
  stubRoutedFetch(routes)
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/app']}>
          <Routes>
            <Route
              path="/app"
              element={
                <OnboardingGate>
                  <p>Dashboard</p>
                </OnboardingGate>
              }
            />
            <Route path="/app/onboarding" element={<p>Wizard</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('OnboardingGate', () => {
  it('redirects to the wizard when onboarding is incomplete and nothing is connected', async () => {
    renderGate({
      '/auth/me': () => jsonResponse(ME),
      '/api/settings/installations': () => jsonResponse([]),
      '/api/clusters': () => jsonResponse([]),
    })
    expect(await screen.findByText('Wizard')).toBeInTheDocument()
  })

  it('renders children once onboarding_completed is true', async () => {
    renderGate({
      '/auth/me': () => jsonResponse({ ...ME, onboarding_completed: true }),
      '/api/settings/installations': () => jsonResponse([]),
      '/api/clusters': () => jsonResponse([]),
    })
    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })

  it('renders children when an installation exists, even if the flag is false', async () => {
    renderGate({
      '/auth/me': () => jsonResponse(ME),
      '/api/settings/installations': () => jsonResponse([makeInstallation()]),
      '/api/clusters': () => jsonResponse([]),
    })
    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })

  it('renders children when a cluster exists, even if the flag is false', async () => {
    renderGate({
      '/auth/me': () => jsonResponse(ME),
      '/api/settings/installations': () => jsonResponse([]),
      '/api/clusters': () => jsonResponse([makeCluster()]),
    })
    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })
})
