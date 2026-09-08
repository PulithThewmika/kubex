import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Settings } from './Settings'
import { AuthProvider } from '../contexts/AuthContext'
import { jsonResponse, makeInstallation, stubRoutedFetch } from '../test/fixtures'

const ME = {
  user_id: 'u1',
  login: 'alice',
  email: 'alice@example.com',
  avatar_url: null,
  org_id: 'o1',
  org_name: 'Acme Corp',
  org_slug: 'acme-corp',
  onboarding_completed: true,
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-search">{location.search}</div>
}

function renderSettings(initialEntry = '/app/settings') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/app/settings" element={<Settings />} />
          </Routes>
          <LocationProbe />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function stubSettingsFetch(overrides: Record<string, () => Response> = {}) {
  stubRoutedFetch({
    '/auth/me': () => jsonResponse(ME),
    '/api/settings/installations': () => jsonResponse([]),
    '/api/settings/api-keys': () => jsonResponse([]),
    '/api/settings/members': () => jsonResponse([{ user_id: 'u1', login: 'alice', avatar_url: null, role: 'owner', joined_at: '2026-08-01T00:00:00Z' }]),
    '/api/settings/slack': () => jsonResponse({ connected: false, workspace_id: null, team_name: null, channels: [] }),
    '/api/clusters': () => jsonResponse([]),
    ...overrides,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Settings page', () => {
  it('shows the General tab by default with org name and slug', async () => {
    stubSettingsFetch()
    renderSettings()

    expect(await screen.findByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('acme-corp')).toBeInTheDocument()
  })

  it('switches to the Connections tab and updates the url', async () => {
    stubSettingsFetch()
    renderSettings()

    fireEvent.click(await screen.findByRole('tab', { name: 'Connections' }))

    const link = await screen.findByRole('link', { name: /connect github/i })
    expect(link).toHaveAttribute('href', 'https://github.com/apps/kubex-dev/installations/new')
    expect(screen.getByTestId('location-search')).toHaveTextContent('?tab=connections')
  })

  it('deep-links to a tab via ?tab=', async () => {
    stubSettingsFetch({
      '/api/settings/installations': () =>
        jsonResponse([makeInstallation({ account_login: 'acme-corp', status: 'active' })]),
    })
    renderSettings('/app/settings?tab=connections')

    expect(await screen.findByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('lands on the Connections tab when redirected back with an installation_id', async () => {
    stubSettingsFetch()
    renderSettings('/app/settings?installation_id=999')

    expect(await screen.findByRole('status')).toHaveTextContent('installation #999 connected successfully')
  })

  it('shows the Clusters section on the Connections tab', async () => {
    stubSettingsFetch()
    renderSettings('/app/settings?tab=connections')

    expect(await screen.findByText(/no clusters connected yet/i)).toBeInTheDocument()
  })

  it('lists API keys and an empty state on the API Keys tab', async () => {
    stubSettingsFetch()
    renderSettings('/app/settings?tab=api-keys')

    expect(await screen.findByText(/no api keys yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create api key/i })).toBeInTheDocument()
  })

  it('lists org members with their role on the Team tab', async () => {
    stubSettingsFetch()
    renderSettings('/app/settings?tab=team')

    expect(await screen.findByText('alice')).toBeInTheDocument()
    expect(screen.getByText('owner')).toBeInTheDocument()
  })
})
