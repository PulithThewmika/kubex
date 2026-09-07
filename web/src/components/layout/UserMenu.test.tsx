import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, stubRoutedFetch } from '../../test/fixtures'
import { AuthProvider } from '../../contexts/AuthContext'
import { UserMenu } from './UserMenu'

const ME = {
  user_id: '1',
  login: 'octocat',
  email: null,
  avatar_url: null,
  org_id: 'org-1',
  org_name: 'Acme',
  org_slug: 'acme',
  onboarding_completed: true,
}

function renderMenu() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <UserMenu />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('UserMenu', () => {
  it('renders nothing until the user is loaded', () => {
    stubRoutedFetch({ '/auth/me': () => new Response(null, { status: 401 }) })
    const { container } = renderMenu()
    expect(container).toBeEmptyDOMElement()
  })

  it('opens the dropdown and shows the login + sign out', async () => {
    stubRoutedFetch({
      '/auth/memberships': () => jsonResponse([{ org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' }]),
      '/auth/me': () => jsonResponse(ME),
    })
    renderMenu()

    const trigger = await screen.findByRole('button', { name: 'User menu' })
    fireEvent.click(trigger)

    expect(screen.getByText('octocat')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('does not render the org switcher for a single-org user', async () => {
    stubRoutedFetch({
      '/auth/memberships': () => jsonResponse([{ org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' }]),
      '/auth/me': () => jsonResponse(ME),
    })
    renderMenu()

    fireEvent.click(await screen.findByRole('button', { name: 'User menu' }))

    await waitFor(() => expect(screen.queryByText('Switch organization')).not.toBeInTheDocument())
  })

  it('signs out and clears the session on click', async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/auth/memberships'))
        return Promise.resolve(jsonResponse([{ org_id: 'org-1', org_name: 'Acme', org_slug: 'acme' }]))
      if (url.startsWith('/auth/me')) return Promise.resolve(jsonResponse(ME))
      if (url.startsWith('/auth/logout')) return Promise.resolve(jsonResponse({ status: 'ok' }))
      return Promise.resolve(new Response(null, { status: 404 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderMenu()

    fireEvent.click(await screen.findByRole('button', { name: 'User menu' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/auth/logout', { method: 'POST', credentials: 'include' }),
    )
  })
})
