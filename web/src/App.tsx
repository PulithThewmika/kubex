import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
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
import { NotFound } from './pages/NotFound'

const queryClient = new QueryClient()

// Route-wide boundary: resetKey on pathname so navigating after a crash on a
// top-level route (RootRoute/Login/NotFound) clears the fallback.
function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
}

function RootRoute() {
  const { isAuthenticated, isLoading, isError, refetch } = useAuth()
  if (isLoading) return null
  if (isError) return <AuthErrorState onRetry={() => refetch()} />
  if (isAuthenticated) return <Navigate to="/app" replace />
  return <Landing />
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <RoutedErrorBoundary>
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
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
