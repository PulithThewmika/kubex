import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../contexts/AuthContext'
import { RequireAuth } from './RequireAuth'

function renderWithAuth(initialPath: string) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/login" element={<p>Login page</p>} />
            <Route
              path="/app"
              element={
                <RequireAuth>
                  <p>Protected content</p>
                </RequireAuth>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('RequireAuth', () => {
  it('redirects to /login?redirect=<path> when unauthenticated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))

    renderWithAuth('/app')

    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })

  it('renders children when authenticated', async () => {
    const me = {
      user_id: '1',
      login: 'octocat',
      email: null,
      avatar_url: null,
      org_id: '2',
      org_name: 'Acme',
      org_slug: 'acme',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(me), { status: 200 })))

    renderWithAuth('/app')

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })
})
