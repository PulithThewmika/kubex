import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, makeDeploymentDetail, stubRoutedFetch } from './test/fixtures'

// App.tsx builds its QueryClient as a module-level singleton, so importing
// it fresh per test (via resetModules) keeps each test's react-query cache
// isolated — otherwise all 5 cases here would share one cache instance.
async function renderApp() {
  vi.resetModules()
  const { default: App } = await import('./App')
  return render(<App />)
}

const ME_RESPONSE = {
  user_id: '1',
  login: 'octocat',
  email: null,
  avatar_url: null,
  org_id: '2',
  org_name: 'Acme',
  org_slug: 'acme',
}

const AUTHENTICATED_ROUTES = {
  '/auth/me': () => jsonResponse(ME_RESPONSE),
  '/api/services': () => jsonResponse([]),
  '/api/deployments/': () => jsonResponse(makeDeploymentDetail()),
  '/api/deployments': () => jsonResponse([]),
  '/api/dora': () => jsonResponse({ deploy_frequency_per_day: null, lead_time_avg_s: null, change_failure_rate: null, mttr_s: null, period: '30d', service: null }),
  '/api/grafana/proxy': () => new Response(null, { status: 200 }),
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('App routing', () => {
  it(
    'redirects an unauthenticated visit to /app to /login',
    async () => {
      stubRoutedFetch({ '/auth/me': () => new Response(null, { status: 401 }) })
      window.history.pushState({}, '', '/app')

      await renderApp()

      expect(await screen.findByRole('link', { name: /sign in with github/i })).toBeInTheDocument()
    },
    // First test in the file pays the one-time cost of vi.resetModules()
    // re-transforming App's whole import graph (router, react-query,
    // recharts-adjacent chart libs pulled in by page components) — under
    // load that alone can approach the 5s default.
    10_000,
  )

  it('renders Overview at /app when authenticated', async () => {
    stubRoutedFetch(AUTHENTICATED_ROUTES)
    window.history.pushState({}, '', '/app')

    await renderApp()

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
  })

  it('redirects the bare / to /app (then to /login when unauthenticated)', async () => {
    stubRoutedFetch({ '/auth/me': () => new Response(null, { status: 401 }) })
    window.history.pushState({}, '', '/')

    await renderApp()

    expect(await screen.findByRole('link', { name: /sign in with github/i })).toBeInTheDocument()
  })

  it('renders ServiceDeepDive at /app/services/:name', async () => {
    stubRoutedFetch(AUTHENTICATED_ROUTES)
    window.history.pushState({}, '', '/app/services/orders')

    await renderApp()

    expect(await screen.findByRole('heading', { name: 'orders' })).toBeInTheDocument()
  })

  it('renders DeployDetail at /app/deployments/:id', async () => {
    stubRoutedFetch(AUTHENTICATED_ROUTES)
    window.history.pushState({}, '', '/app/deployments/42')

    await renderApp()

    expect(await screen.findByRole('heading', { name: 'Health evidence' })).toBeInTheDocument()
  })

  it('renders Chat at /app/chat', async () => {
    stubRoutedFetch(AUTHENTICATED_ROUTES)
    window.history.pushState({}, '', '/app/chat')

    await renderApp()

    expect(await screen.findByPlaceholderText(/ask about/i)).toBeInTheDocument()
  })

  it('falls through gracefully on an unknown route without crashing', async () => {
    stubRoutedFetch(AUTHENTICATED_ROUTES)
    window.history.pushState({}, '', '/this-route-does-not-exist')

    const { container } = await renderApp()

    // No route (not even the AppLayout wrapper) matches an unregistered
    // path today, so nothing renders — the important thing is it doesn't throw.
    expect(screen.queryByRole('heading', { name: 'Overview' })).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/ask about/i)).not.toBeInTheDocument()
    expect(container).toBeInTheDocument()
  })
})
