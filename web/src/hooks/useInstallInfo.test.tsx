import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useInstallInfo } from './useInstallInfo'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useInstallInfo', () => {
  it('fetches /api/install-info', async () => {
    const info = {
      ingest_public_url: 'https://ingest.example.com',
      agent_namespace: 'kubex-agent',
      chart_repo_url: 'https://github.com/PulithThewmika/kubex.git',
      chart_path: 'deploy/helm/cluster-agent',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(info), { status: 200 })))

    const { result } = renderHook(() => useInstallInfo(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(info)
    expect(fetch).toHaveBeenCalledWith('/api/install-info', expect.objectContaining({ credentials: 'include' }))
  })
})
