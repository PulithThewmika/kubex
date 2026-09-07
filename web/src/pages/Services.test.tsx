import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Services } from './Services'
import { jsonResponse, makeCluster, makeService, stubRoutedFetch } from '../test/fixtures'

function renderServices(initialEntry = '/app/services') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/services" element={<Services />} />
          <Route path="/app/services/:name" element={<div>Deep Dive</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Services page', () => {
  it('renders every service card with its connection status', async () => {
    stubRoutedFetch({
      '/api/services': () =>
        jsonResponse([
          makeService({ id: 1, name: 'orders' }),
          makeService({
            id: 2,
            name: 'payments',
            integration_status: { ci: true, cd: null, metrics: null, available_features: [] },
          }),
        ]),
      '/api/clusters': () => jsonResponse([]),
    })

    renderServices()

    expect(await screen.findByText('orders')).toBeInTheDocument()
    expect(screen.getByText('payments')).toBeInTheDocument()

    // Both cards show all three connection tiers.
    expect(screen.getAllByLabelText(/^CI:/)).toHaveLength(2)
    expect(screen.getAllByLabelText(/^CD:/)).toHaveLength(2)
    expect(screen.getByLabelText('CD: not connected')).toBeInTheDocument()
  })

  it('filters by search query', async () => {
    stubRoutedFetch({
      '/api/services': () =>
        jsonResponse([makeService({ id: 1, name: 'orders' }), makeService({ id: 2, name: 'payments' })]),
      '/api/clusters': () => jsonResponse([]),
    })

    renderServices()

    await screen.findByText('orders')
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'pay' } })

    expect(screen.queryByText('orders')).not.toBeInTheDocument()
    expect(screen.getByText('payments')).toBeInTheDocument()
  })

  it('sorts by deploy frequency', async () => {
    stubRoutedFetch({
      '/api/services': () =>
        jsonResponse([
          makeService({ id: 1, name: 'low', deploy_count_30d: 1 }),
          makeService({ id: 2, name: 'high', deploy_count_30d: 20 }),
        ]),
      '/api/clusters': () => jsonResponse([]),
    })

    renderServices('/app/services?sort=frequency')

    const cards = await screen.findAllByText(/^(low|high)$/)
    expect(cards.map((c) => c.textContent)).toEqual(['high', 'low'])
  })

  it('filters by cluster when assignments exist', async () => {
    stubRoutedFetch({
      '/api/services': () =>
        jsonResponse([
          makeService({ id: 1, name: 'orders', cluster_id: 'c1', cluster_name: 'prod' }),
          makeService({ id: 2, name: 'payments', cluster_id: null }),
        ]),
      '/api/clusters': () => jsonResponse([makeCluster({ id: 'c1', name: 'prod' })]),
    })

    renderServices()

    await screen.findByText('orders')
    fireEvent.change(screen.getByRole('combobox', { name: /cluster/i }), { target: { value: 'c1' } })

    expect(screen.getByText('orders')).toBeInTheDocument()
    expect(screen.queryByText('payments')).not.toBeInTheDocument()
  })

  it('shows a filtered empty state', async () => {
    stubRoutedFetch({
      '/api/services': () => jsonResponse([makeService({ id: 1, name: 'orders' })]),
      '/api/clusters': () => jsonResponse([]),
    })

    renderServices()

    await screen.findByText('orders')
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'zzz' } })

    expect(screen.getByText(/no services match the current filters/i)).toBeInTheDocument()
  })

  it('shows an error state when the services request fails', async () => {
    stubRoutedFetch({
      '/api/services': () => new Response(null, { status: 500 }),
      '/api/clusters': () => jsonResponse([]),
    })

    renderServices()

    expect(await screen.findByText(/failed to load services/i)).toBeInTheDocument()
  })
})
