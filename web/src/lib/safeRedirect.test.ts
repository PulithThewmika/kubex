import { describe, expect, it } from 'vitest'
import { safeRedirectPath } from './safeRedirect'

describe('safeRedirectPath', () => {
  it('allows a same-site relative path', () => {
    expect(safeRedirectPath('/app/services/orders')).toBe('/app/services/orders')
  })

  it('falls back to /app for null or empty input', () => {
    expect(safeRedirectPath(null)).toBe('/app')
    expect(safeRedirectPath('')).toBe('/app')
  })

  it('rejects an absolute URL to another host', () => {
    expect(safeRedirectPath('https://evil.com/phish')).toBe('/app')
  })

  it('rejects a protocol-relative URL', () => {
    expect(safeRedirectPath('//evil.com')).toBe('/app')
  })

  it('rejects a backslash variant browsers normalize to protocol-relative', () => {
    expect(safeRedirectPath('/\\evil.com')).toBe('/app')
  })

  it('rejects a path with no leading slash', () => {
    expect(safeRedirectPath('evil.com')).toBe('/app')
  })
})
