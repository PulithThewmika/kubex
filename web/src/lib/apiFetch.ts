import { safeRedirectPath } from './safeRedirect'

/**
 * Thin wrapper around fetch for same-origin API calls: always sends the
 * session cookie, and on a 401 redirects to /login (preserving the current
 * path as ?redirect=) instead of letting every caller handle it separately.
 */
export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, { ...init, credentials: 'include' })
  if (res.status === 401) {
    const redirect = encodeURIComponent(safeRedirectPath(window.location.pathname + window.location.search))
    window.location.assign(`/login?redirect=${redirect}`)
  }
  return res
}
