import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from './apiFetch'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('always sends credentials: include', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/services')

    expect(fetchMock).toHaveBeenCalledWith('/api/services', { credentials: 'include' })
  })

  it('preserves caller-supplied init options alongside credentials', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/chat', { method: 'POST', body: '{}' })

    expect(fetchMock).toHaveBeenCalledWith('/api/chat', {
      method: 'POST',
      body: '{}',
      credentials: 'include',
    })
  })

  it('redirects to /login on a 401 without throwing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))
    const assignMock = vi.fn()
    vi.stubGlobal('location', { ...window.location, pathname: '/app/services', search: '', assign: assignMock })

    const res = await apiFetch('/api/services')

    expect(res.status).toBe(401)
    expect(assignMock).toHaveBeenCalledWith('/login?redirect=%2Fapp%2Fservices')
  })

  it('does not redirect on a non-401 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })))
    const assignMock = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign: assignMock })

    await apiFetch('/api/services')

    expect(assignMock).not.toHaveBeenCalled()
  })
})
