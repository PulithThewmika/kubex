import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RotateTokenDialog } from './RotateTokenDialog'
import { jsonResponse, makeCluster } from '../test/fixtures'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderDialog(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const cluster = makeCluster({ id: 'c1', name: 'prod' })
  return render(
    <QueryClientProvider client={queryClient}>
      <RotateTokenDialog cluster={cluster} onClose={onClose} />
    </QueryClientProvider>,
  )
}

describe('RotateTokenDialog', () => {
  it('requires confirmation before rotating', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchSpy)

    renderDialog()

    expect(screen.getByText(/10-minute grace period/i)).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('rotates the token and shows the new one once', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ token: 'kbx_new_token', grace_period_expires_at: '2026-08-29T10:10:00Z' }),
      ),
    )

    renderDialog()
    fireEvent.click(screen.getByRole('button', { name: /^rotate token$/i }))

    expect(await screen.findByText('kbx_new_token')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      '/api/clusters/c1/rotate-token',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })

  it('shows an error when rotation fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 404 })))

    renderDialog()
    fireEvent.click(screen.getByRole('button', { name: /^rotate token$/i }))

    expect(await screen.findByText(/failed to rotate token/i)).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked without rotating', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchSpy)
    const onClose = vi.fn()

    renderDialog(onClose)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onClose).toHaveBeenCalledOnce()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
