import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Settings } from './Settings'
import { jsonResponse, makeInstallation, stubRoutedFetch } from '../test/fixtures'

function renderSettings(initialEntry = '/app/settings') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/settings" element={<Settings />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function stubSettingsFetch(installations: unknown[] = []) {
  stubRoutedFetch({
    '/api/settings/installations': () => jsonResponse(installations),
    '/api/clusters': () => jsonResponse([]),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Settings page', () => {
  it('renders a Connect GitHub button linking to the app install page', async () => {
    stubSettingsFetch()

    renderSettings()

    const link = await screen.findByRole('link', { name: /connect github/i })
    expect(link).toHaveAttribute('href', 'https://github.com/apps/deploylens/installations/new')
  })

  it('renders installations with status badges', async () => {
    stubSettingsFetch([
      makeInstallation({ account_login: 'acme-corp', status: 'active' }),
      makeInstallation({ id: '2', account_login: 'other-org', status: 'suspended' }),
    ])

    renderSettings()

    expect(await screen.findByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('other-org')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('suspended')).toBeInTheDocument()
  })

  it('shows an empty state when there are no installations', async () => {
    stubSettingsFetch()

    renderSettings()

    expect(await screen.findByText(/no github app installations yet/i)).toBeInTheDocument()
  })

  it('shows a confirmation banner when redirected back with an installation_id', async () => {
    stubSettingsFetch()

    renderSettings('/app/settings?installation_id=999')

    expect(await screen.findByRole('status')).toHaveTextContent('installation #999 connected successfully')
  })

  it('does not show the empty state while the redirect banner is up and the list is still empty', async () => {
    stubSettingsFetch()

    renderSettings('/app/settings?installation_id=999')

    await screen.findByRole('status')
    expect(screen.queryByText(/no github app installations yet/i)).not.toBeInTheDocument()
  })

  it('renders the Clusters section', async () => {
    stubSettingsFetch()

    renderSettings()

    expect(await screen.findByText(/no clusters connected yet/i)).toBeInTheDocument()
  })
})
