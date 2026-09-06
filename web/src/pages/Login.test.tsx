import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Login } from './Login'

describe('Login', () => {
  it('links Sign in with GitHub to /auth/github with a default redirect', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Login />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /sign in with github/i })
    expect(link).toHaveAttribute('href', '/auth/github?redirect=%2Fapp')
  })

  it('preserves a valid ?redirect= query param', () => {
    render(
      <MemoryRouter initialEntries={['/login?redirect=/app/services/orders']}>
        <Login />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /sign in with github/i })
    expect(link).toHaveAttribute('href', '/auth/github?redirect=%2Fapp%2Fservices%2Forders')
  })

  it('discards an unsafe ?redirect= query param', () => {
    render(
      <MemoryRouter initialEntries={['/login?redirect=https://evil.com']}>
        <Login />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /sign in with github/i })
    expect(link).toHaveAttribute('href', '/auth/github?redirect=%2Fapp')
  })
})
