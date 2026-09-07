import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AddClusterModal } from './AddClusterModal'
import { jsonResponse, makeCluster } from '../test/fixtures'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderModal(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AddClusterModal onClose={onClose} />
    </QueryClientProvider>,
  )
}

describe('AddClusterModal', () => {
  it('walks through name -> token -> install method -> waiting -> connected', async () => {
    const created = { id: 'c1', name: 'prod', token: 'kbx_shown_once', created_at: '2026-08-29T10:00:00Z' }
    let heartbeatConnected = false
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === 'POST') return Promise.resolve(jsonResponse(created, 201))
        return Promise.resolve(
          jsonResponse(heartbeatConnected ? [makeCluster({ id: 'c1', status: 'connected' })] : []),
        )
      }),
    )

    renderModal()

    // Step 1: name
    fireEvent.change(screen.getByPlaceholderText('production'), { target: { value: 'prod' } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 2: token, shown once
    expect(await screen.findByText('kbx_shown_once')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    // Step 3: install method tabs, default kubectl
    expect(await screen.findByText(/kubectl apply -f -/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Helm' }))
    expect(await screen.findByText(/helm install prod/)).toBeInTheDocument()

    // GitOps snippet is meant to be committed to Git — must never embed the
    // real token in plaintext, unlike the one-shot kubectl/Helm commands.
    fireEvent.click(screen.getByRole('button', { name: 'GitOps' }))
    const gitopsBlock = await screen.findByText(/cluster-agent\.yaml/)
    expect(gitopsBlock.textContent).not.toContain('kbx_shown_once')

    fireEvent.click(screen.getByRole('button', { name: /i've installed it/i }))

    // Step 4: waiting, then connected once the poll sees status=connected
    expect(await screen.findByText(/waiting for the agent's first heartbeat/i)).toBeInTheDocument()
    heartbeatConnected = true
    await waitFor(() => expect(screen.getByText('Connected')).toBeInTheDocument(), { timeout: 5000 })
  })

  it('shows an error if cluster creation fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({ detail: 'A cluster with this name already exists' }, 409))),
    )

    renderModal()

    fireEvent.change(screen.getByPlaceholderText('production'), { target: { value: 'prod' } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
  })

  it('calls onClose when the close button is clicked', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(jsonResponse([]))))
    const onClose = vi.fn()

    renderModal(onClose)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalledOnce()
  })
})
