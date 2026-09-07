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
  it('shows a Connect Prometheus fallback when the proxy request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 502 })))

    renderPanel()

    await waitFor(() => expect(screen.getByText('Metrics not available')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /connect prometheus/i })).toHaveAttribute(
      'href',
      '/app/settings?tab=connections',
    )
  })

  it('does not show the fallback while the request is in flight', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    renderPanel()

    expect(screen.queryByText('Metrics not available')).not.toBeInTheDocument()
    expect(screen.getByText(/loading error rate/i)).toBeInTheDocument()
  })
})
