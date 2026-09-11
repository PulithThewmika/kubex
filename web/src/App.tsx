import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation, useNavigationType } from 'react-router-dom'
import { AuthErrorState } from './components/auth/AuthErrorState'
import { RequireAuth } from './components/auth/RequireAuth'
import { AppLayout } from './components/layout/AppLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { OnboardingGate } from './components/onboarding/OnboardingGate'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { Onboarding } from './pages/Onboarding'
import { Overview } from './pages/Overview'
import { ServiceDeepDive } from './pages/ServiceDeepDive'
import { DeployDetail } from './pages/DeployDetail'
import { Chat } from './pages/Chat'
import { Alerts } from './pages/Alerts'
import { Services } from './pages/Services'
import { Settings } from './pages/Settings'
import { Privacy } from './pages/Privacy'
import { Terms } from './pages/Terms'
import { NotFound } from './pages/NotFound'

const queryClient = new QueryClient()

// Route-wide boundary: resetKey on pathname so navigating after a crash on a
// top-level route (RootRoute/Login/NotFound) clears the fallback.
function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
}

// Module-level (survives across route changes, resets on a full page
// reload) — scroll position of each history entry, keyed by its
// react-router location.key, so a POP navigation can restore it. Native
// browser scroll restoration is unreliable here because the landing page's
// height keeps changing after mount (GSAP ScrollTrigger, lazy content), so
// the browser often restores against a too-short document and clamps to 0.
const scrollPositions = new Map<string, number>()

// Scroll back to the top on a new (PUSH) navigation — without this,
// deep-linking from a scrolled list into a detail page lands you mid-page.
// On a POP (browser/programmatic back), restore the scroll position the
// page we're returning to had when we left it, instead of jumping to the
// top or leaving it at 0.
function ScrollToTop() {
  const location = useLocation()
  const navigationType = useNavigationType()

  // Runs on every location change; the cleanup fires right before the
  // *next* change, capturing the scroll position of the page being left
  // under the key it still had at that point.
  useEffect(() => {
    return () => {
      if (typeof window.scrollY === 'number') {
        scrollPositions.set(location.key, window.scrollY)
      }
    }
  }, [location.key])

  useEffect(() => {
    // jsdom has no real scroll; guard so tests don't trip on "Not implemented".
    if (typeof window.scrollTo !== 'function') return

    if (navigationType === 'POP') {
      const saved = scrollPositions.get(location.key)
      if (saved !== undefined) {
        // Defer a frame so the new route's content (and any GSAP layout)
        // has mounted before we scroll, or the restore can clamp to 0.
        requestAnimationFrame(() => {
          try {
            window.scrollTo(0, saved)
          } catch {
            /* no-op */
          }
        })
        return
      }
    }

    try {
      window.scrollTo(0, 0)
    } catch {
      /* no-op */
    }
  }, [location.pathname, location.key, navigationType])

  return null
}

// The landing page is the front door for everyone. A logged-in visitor still
// sees it at `/` and clicks through to the app (the hero CTA becomes "Go to
// dashboard"); only a genuine backend failure short-circuits to the retry state.
function RootRoute() {
  const { isAuthenticated, isLoading, isError, refetch } = useAuth()
  if (isLoading) return null
  if (isError) return <AuthErrorState onRetry={() => refetch()} />
  return <Landing isAuthenticated={isAuthenticated} />
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <ScrollToTop />
            <RoutedErrorBoundary>
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/terms" element={<Terms />} />
                <Route
                  path="/app"
                  element={
                    <RequireAuth>
                      <AppLayout />
                    </RequireAuth>
                  }
                >
                  <Route
                    index
                    element={
                      <OnboardingGate>
                        <Overview />
                      </OnboardingGate>
                    }
                  />
                  <Route path="onboarding" element={<Onboarding />} />
                  <Route path="services" element={<Services />} />
                  <Route path="services/:name" element={<ServiceDeepDive />} />
                  <Route path="alerts" element={<Alerts />} />
                  <Route path="deployments/:id" element={<DeployDetail />} />
                  <Route path="chat" element={<Chat />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="*" element={<NotFound />} />
                </Route>
                <Route path="*" element={<NotFound />} />
              </Routes>
            </RoutedErrorBoundary>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
