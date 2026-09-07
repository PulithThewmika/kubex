import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Alerts } from './Alerts'
import { jsonResponse, makeAlert, stubRoutedFetch } from '../test/fixtures'

function renderAlerts(initialEntry = '/app/alerts') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/alerts" element={<Alerts />} />
          <Route path="/app/deployments/:id" element={<div>Deployment Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Alerts page', () => {
  it('shows active alerts by default with severity, service and a deployment link', async () => {
    stubRoutedFetch({
      '/api/alerts': () =>
        jsonResponse([
          makeAlert({ id: 1, title: 'Error rate spike', service_name: 'orders', deployment_id: 42 }),
          makeAlert({ id: 2, title: 'Old resolved one', resolved_at: '2026-08-29T11:00:00Z' }),
        ]),
    })

    renderAlerts()

    expect(await screen.findByText('Error rate spike')).toBeInTheDocument()
    expect(screen.queryByText('Old resolved one')).not.toBeInTheDocument()
    expect(screen.getByText('orders')).toBeInTheDocument()
    expect(screen.getByLabelText('Severity: critical')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /deployment #42/i })).toHaveAttribute(
      'href',
      '/app/deployments/42',
    )
  })

  it('shows resolved alerts with a resolution duration when filtered', async () => {
    stubRoutedFetch({
      '/api/alerts': () =>
        jsonResponse([
          makeAlert({
            id: 3,
            title: 'Recovered latency',
            fired_at: '2026-08-29T10:00:00Z',
            resolved_at: '2026-08-29T10:30:00Z',
          }),
        ]),
    })

    renderAlerts('/app/alerts?status=resolved')

    expect(await screen.findByText('Recovered latency')).toBeInTheDocument()
    expect(screen.getByText(/resolved in/i)).toHaveTextContent('30 minutes')
  })

  it('renders an empty state when there are no active alerts', async () => {
    stubRoutedFetch({
      '/api/alerts': () => jsonResponse([]),
    })

    renderAlerts()

    expect(await screen.findByRole('heading', { name: /all clear/i })).toBeInTheDocument()
  })

  it('shows an error state when the alerts request fails', async () => {
    stubRoutedFetch({
      '/api/alerts': () => new Response(null, { status: 500 }),
    })

    renderAlerts()

    expect(await screen.findByText(/failed to load alerts/i)).toBeInTheDocument()
  })
})
