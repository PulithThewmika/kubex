import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
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

// Scroll back to the top on every navigation — without this, deep-linking
// from a scrolled list into a detail page lands you mid-page.
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    // jsdom has no real scroll; guard so tests don't trip on "Not implemented".
    if (typeof window.scrollTo === 'function') {
      try {
        window.scrollTo(0, 0)
      } catch {
        /* no-op */
      }
    }
  }, [pathname])
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
