import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useClusters } from './useClusters'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useClusters', () => {
  it('fetches clusters from /api/clusters', async () => {
    const clusters = [{ id: '1', name: 'prod', status: 'connected' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(clusters), { status: 200 })))

    const { result } = renderHook(() => useClusters(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(clusters)
    expect(fetch).toHaveBeenCalledWith('/api/clusters', expect.objectContaining({ credentials: 'include' }))
  })

  it('surfaces a fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })))

    const { result } = renderHook(() => useClusters(), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
