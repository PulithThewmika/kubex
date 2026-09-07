import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, stubRoutedFetch } from '../test/fixtures'
import { Onboarding } from './Onboarding'

function renderWizard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/app/onboarding']}>
        <Routes>
          <Route path="/app/onboarding" element={<Onboarding />} />
          <Route path="/app" element={<p>Dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const BASE_ROUTES = {
  '/api/settings/installations': () => jsonResponse([]),
  '/api/clusters': () => jsonResponse([]),
  '/api/install-info': () =>
    jsonResponse({ ingest_public_url: 'https://kubex.example', agent_namespace: 'kubex-agent', chart_repo_url: 'x', chart_path: 'y' }),
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Onboarding wizard', () => {
  it('steps forward through all four steps', async () => {
    stubRoutedFetch(BASE_ROUTES)
    renderWizard()

    expect(await screen.findByRole('heading', { name: 'Connect your repositories' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: 'How do you deploy?' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: 'Connect your metrics' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: "You're set" })).toBeInTheDocument()
  })

  it('marks onboarding complete and navigates to the dashboard on "Skip setup"', async () => {
    const completeCall = vi.fn(() => new Response(null, { status: 204 }))
    stubRoutedFetch({ ...BASE_ROUTES, '/api/settings/onboarding/complete': completeCall })
    renderWizard()

    fireEvent.click(await screen.findByRole('button', { name: 'Skip setup' }))

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    expect(completeCall).toHaveBeenCalled()
  })

  it('lets a step be skipped individually', async () => {
    stubRoutedFetch(BASE_ROUTES)
    renderWizard()

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: 'How do you deploy?' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Skip this step' }))
    expect(screen.getByRole('heading', { name: 'Connect your metrics' })).toBeInTheDocument()
  })

  it('"Skip this step" overrides a selection made on that step', async () => {
    stubRoutedFetch(BASE_ROUTES)
    renderWizard()

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))
    fireEvent.click(screen.getByText('GitHub Deployments'))
    fireEvent.click(screen.getByRole('button', { name: 'Skip this step' }))
    fireEvent.click(screen.getByRole('button', { name: 'Skip this step' }))

    expect(screen.getByRole('heading', { name: "You're set" })).toBeInTheDocument()
    expect(screen.getAllByText('Not configured yet')).toHaveLength(2)
  })

  it('does not count a pending cluster as connected in the summary', async () => {
    stubRoutedFetch({
      ...BASE_ROUTES,
      '/api/clusters': () =>
        jsonResponse([
          { id: 'c1', name: 'edge', status: 'pending', agent_version: null, argocd_version: null, argocd_status: null, prometheus_status: null, last_heartbeat: null, created_at: '2026-09-07T00:00:00Z' },
        ]),
    })
    renderWizard()

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByRole('heading', { name: "You're set" })).toBeInTheDocument()
    expect(screen.getByText('No cluster connected')).toBeInTheDocument()
  })
})
