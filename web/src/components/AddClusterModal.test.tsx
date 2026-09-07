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
    expect(await screen.findByText(/helm install 'prod'/)).toBeInTheDocument()

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

  it('ignores close while cluster creation is in flight, so the once-only token is never lost', async () => {
    let resolveCreate: (r: Response) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise<Response>((resolve) => (resolveCreate = resolve))),
    )
    const onClose = vi.fn()

    renderModal(onClose)
    fireEvent.change(screen.getByPlaceholderText('production'), { target: { value: 'prod' } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    // useMutation's isPending flip is batched via a microtask — wait for it
    // to actually reach the DOM before asserting the close guard sees it.
    await screen.findByRole('button', { name: /creating/i })
    fireEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).not.toHaveBeenCalled()

    resolveCreate(jsonResponse({ id: 'c1', name: 'prod', token: 'kbx_shown_once', created_at: '2026-08-29T10:00:00Z' }, 201))
    expect(await screen.findByText('kbx_shown_once')).toBeInTheDocument()
  })

  it('shell-quotes the cluster name in the Helm command, including embedded quotes', async () => {
    const created = { id: 'c1', name: "prod'; rm -rf /", token: 'kbx_shown_once', created_at: '2026-08-29T10:00:00Z' }
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(created, 201))))

    renderModal()
    fireEvent.change(screen.getByPlaceholderText('production'), { target: { value: "prod'; rm -rf /" } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    await screen.findByText('kbx_shown_once')
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Helm' }))

    const helmBlock = await screen.findByText(/helm install/)
    expect(helmBlock.textContent).toContain(`'prod'\\''; rm -rf /'`)
  })

  it('shows a retry option if heartbeat polling fails', async () => {
    const created = { id: 'c1', name: 'prod', token: 'kbx_shown_once', created_at: '2026-08-29T10:00:00Z' }
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === 'POST') return Promise.resolve(jsonResponse(created, 201))
        return Promise.resolve(new Response(null, { status: 500 }))
      }),
    )

    renderModal()
    fireEvent.change(screen.getByPlaceholderText('production'), { target: { value: 'prod' } })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    await screen.findByText('kbx_shown_once')
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    fireEvent.click(screen.getByRole('button', { name: /i've installed it/i }))

    expect(await screen.findByText(/couldn't check the cluster's status/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
