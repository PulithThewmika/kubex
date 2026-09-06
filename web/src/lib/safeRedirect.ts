const DEFAULT_REDIRECT_PATH = '/app'

/**
 * Mirrors the backend's `_safe_redirect_path` (services/ingest/app/routers/auth.py):
 * only same-site relative paths are allowed, so a `?redirect=` value can't be
 * turned into an open redirect (an absolute URL, a protocol-relative
 * "//evil.com", or a backslash variant browsers normalize to "//evil.com").
 */
export function safeRedirectPath(redirect: string | null | undefined): string {
  if (redirect && !redirect.includes('\\')) {
    let parsed: URL | null = null
    try {
      parsed = new URL(redirect, window.location.origin)
    } catch {
      parsed = null
    }
    if (redirect.startsWith('/') && !redirect.startsWith('//') && parsed && parsed.origin === window.location.origin) {
      return redirect
    }
  }
  return DEFAULT_REDIRECT_PATH
}
