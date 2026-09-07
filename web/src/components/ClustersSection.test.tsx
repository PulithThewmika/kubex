import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ClustersSection } from './ClustersSection'
import { makeCluster } from '../test/fixtures'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderSection(onAddCluster = vi.fn(), onRotateToken = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ClustersSection onAddCluster={onAddCluster} onRotateToken={onRotateToken} />
    </QueryClientProvider>,
  )
}

describe('ClustersSection', () => {
  it('renders clusters with status badge, component status, and last heartbeat', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            makeCluster({ name: 'prod', status: 'connected', argocd_status: 'found', prometheus_status: 'not_found' }),
          ]),
          { status: 200 },
        ),
      ),
    )

    renderSection()

    expect(await screen.findByText('prod')).toBeInTheDocument()
    expect(screen.getByText('connected')).toBeInTheDocument()
    expect(screen.getByText(/argocd: found/i)).toBeInTheDocument()
    expect(screen.getByText(/prometheus: not found/i)).toBeInTheDocument()
    expect(screen.getByText(/last heartbeat/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no clusters', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))

    renderSection()

    expect(await screen.findByText(/no clusters connected yet/i)).toBeInTheDocument()
  })

  it('calls onAddCluster when the Add cluster button is clicked', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))
    const onAddCluster = vi.fn()

    renderSection(onAddCluster)
    fireEvent.click(await screen.findByRole('button', { name: /add cluster/i }))

    expect(onAddCluster).toHaveBeenCalledOnce()
  })

  it('calls onRotateToken with the cluster when Rotate token is clicked', async () => {
    const cluster = makeCluster()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([cluster]), { status: 200 })))
    const onRotateToken = vi.fn()

    renderSection(vi.fn(), onRotateToken)
    fireEvent.click(await screen.findByRole('button', { name: /rotate token/i }))

    expect(onRotateToken).toHaveBeenCalledWith(cluster)
  })
})
