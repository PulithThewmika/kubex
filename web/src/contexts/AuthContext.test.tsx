import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('AuthContext', () => {
  it('sets user state and isAuthenticated on a 200 from /auth/me', async () => {
    const me = {
      user_id: '1',
      login: 'octocat',
      email: 'octo@example.com',
      avatar_url: null,
      org_id: '2',
      org_name: 'Acme',
      org_slug: 'acme',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(me), { status: 200 })))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(me)
    expect(fetch).toHaveBeenCalledWith('/auth/me', { credentials: 'include' })
  })

  it('sets unauthenticated state on a 401 from /auth/me', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('clears user state after logout', async () => {
    const me = {
      user_id: '1',
      login: 'octocat',
      email: null,
      avatar_url: null,
      org_id: '2',
      org_name: 'Acme',
      org_slug: 'acme',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(me), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true))

    await result.current.logout()

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false))
    expect(fetchMock).toHaveBeenLastCalledWith('/auth/logout', { method: 'POST', credentials: 'include' })
  })

  it('does not clear user state when the logout request fails', async () => {
    const me = {
      user_id: '1',
      login: 'octocat',
      email: null,
      avatar_url: null,
      org_id: '2',
      org_name: 'Acme',
      org_slug: 'acme',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(me), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 500 }))
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true))

    await expect(result.current.logout()).rejects.toThrow('Failed to log out: 500')
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('sets isError (not isAuthenticated: derived-false-as-unauth) on a 5xx from /auth/me', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isError).toBe(true)
    expect(result.current.isAuthenticated).toBe(false)
  })
})
