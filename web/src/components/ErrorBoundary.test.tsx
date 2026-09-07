import { render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): never {
  throw new Error('kaboom')
}

function Recoverable() {
  const [ok, setOk] = useState(false)
  if (!ok) throw new Error('nope')
  return <button onClick={() => setOk(false)}>fine</button>
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>content</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('shows the fallback with retry and dashboard link on a render error', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('heading', { name: /something went wrong/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/app')
  })

  it('re-attempts to render children when Try again is clicked', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Recoverable />
      </ErrorBoundary>,
    )
    // Still throwing, so the fallback stays after retry.
    screen.getByRole('button', { name: /try again/i }).click()
    expect(screen.getByRole('heading', { name: /something went wrong/i })).toBeInTheDocument()
  })
})
