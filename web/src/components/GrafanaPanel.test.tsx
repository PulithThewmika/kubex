import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GrafanaPanel } from './GrafanaPanel'

function renderPanel() {
  return render(
    <MemoryRouter>
      <GrafanaPanel uid="deploy-timeline" panelId={1} service="orders" title="Error Rate" />
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('GrafanaPanel', () => {
  it('distinguishes "no metrics source connected" (503) with a working connect link', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })))

    renderPanel()

    await waitFor(() => expect(screen.getByText('No metrics source connected')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /connect a cluster/i })).toHaveAttribute(
      'href',
      '/app/settings?tab=connections',
    )
  })

  it('shows a render failure for a non-503 error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 502 })))

    renderPanel()

    await waitFor(() => expect(screen.getByText('Panel failed to load')).toBeInTheDocument())
    expect(screen.queryByText('No metrics source connected')).not.toBeInTheDocument()
  })

  it('does not show a fallback while the request is in flight', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderPanel()

    expect(screen.queryByText('Panel failed to load')).not.toBeInTheDocument()
    expect(screen.getByText(/loading error rate/i)).toBeInTheDocument()
  })

  it('renders the PNG from a single fetch (no second render request)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(['png']),
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })

    renderPanel()

    await waitFor(() => expect(screen.getByRole('img', { name: 'Error Rate' })).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
