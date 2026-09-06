import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Settings } from './Settings'
import { makeInstallation } from '../test/fixtures'

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

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Settings page', () => {
  it('renders a Connect GitHub button linking to the app install page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))

    renderSettings()

    const link = await screen.findByRole('link', { name: /connect github/i })
    expect(link).toHaveAttribute('href', 'https://github.com/apps/deploylens/installations/new')
  })

  it('renders installations with status badges', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            makeInstallation({ account_login: 'acme-corp', status: 'active' }),
            makeInstallation({ id: '2', account_login: 'other-org', status: 'suspended' }),
          ]),
          { status: 200 },
        ),
      ),
    )

    renderSettings()

    expect(await screen.findByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('other-org')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('suspended')).toBeInTheDocument()
  })

  it('shows an empty state when there are no installations', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))

    renderSettings()

    expect(await screen.findByText(/no github app installations yet/i)).toBeInTheDocument()
  })

  it('shows a confirmation banner when redirected back with an installation_id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))

    renderSettings('/app/settings?installation_id=999')

    expect(await screen.findByRole('status')).toHaveTextContent('installation #999 connected successfully')
  })
})
