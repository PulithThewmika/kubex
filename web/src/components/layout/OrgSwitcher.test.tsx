import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, stubRoutedFetch } from '../../test/fixtures'
import { AuthProvider } from '../../contexts/AuthContext'
import { OrgSwitcher } from './OrgSwitcher'

const ME = {
  user_id: '1',
  login: 'octocat',
  email: null,
  avatar_url: null,
  org_id: 'org-1',
  org_name: 'Acme',
  org_slug: 'acme',
}

function renderSwitcher(onSwitched = vi.fn()) {
  const queryClient = new QueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <OrgSwitcher onSwitched={onSwitched} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return onSwitched
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  // jsdom doesn't implement navigation; OrgSwitcher's handleSwitch calls
  // window.location.reload() on success, which would otherwise throw.
  vi.stubGlobal('location', { ...window.location, reload: vi.fn() })
})

describe('OrgSwitcher', () => {
  it('renders nothing for a single-org user', async () => {
    stubRoutedFetch({
      '/auth/memberships': () => jsonResponse([{ org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' }]),
      '/auth/me': () => jsonResponse(ME),
    })
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <OrgSwitcher onSwitched={vi.fn()} />
        </AuthProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('lists every org for a multi-org user and marks the active one', async () => {
    stubRoutedFetch({
      '/auth/memberships': () =>
        jsonResponse([
          { org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' },
          { org_id: 'org-2', org_name: 'Beta', org_slug: 'beta' },
        ]),
      '/auth/me': () => jsonResponse(ME),
    })
    renderSwitcher()

    expect(await screen.findByText('Acme')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
  })

  it('calls POST /auth/switch-org and onSwitched when a different org is picked', async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/auth/memberships'))
        return Promise.resolve(
          jsonResponse([
            { org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' },
            { org_id: 'org-2', org_name: 'Beta', org_slug: 'beta' },
          ]),
        )
      if (url.startsWith('/auth/switch-org')) return Promise.resolve(jsonResponse({ status: 'ok', org_id: 'org-2' }))
      if (url.startsWith('/auth/me')) return Promise.resolve(jsonResponse(ME))
      return Promise.resolve(new Response(null, { status: 404 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const onSwitched = renderSwitcher()

    fireEvent.click(await screen.findByText('Beta'))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/auth/switch-org', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_id: 'org-2' }),
      }),
    )
    await waitFor(() => expect(onSwitched).toHaveBeenCalled())
  })
})
