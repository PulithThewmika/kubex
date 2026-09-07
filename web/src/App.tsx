import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthErrorState } from './components/auth/AuthErrorState'
import { RequireAuth } from './components/auth/RequireAuth'
import { AppLayout } from './components/layout/AppLayout'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { OnboardingGate } from './components/onboarding/OnboardingGate'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { Onboarding } from './pages/Onboarding'
import { Overview } from './pages/Overview'
import { ServiceDeepDive } from './pages/ServiceDeepDive'
import { DeployDetail } from './pages/DeployDetail'
import { Chat } from './pages/Chat'
import { Alerts } from './pages/Alerts'
import { Settings } from './pages/Settings'

const queryClient = new QueryClient()

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <h1 className="font-heading text-2xl">{title}</h1>
    </div>
  )
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
      <AuthProvider>
        <BrowserRouter>
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
              <Route path="services" element={<PlaceholderPage title="Services" />} />
              <Route path="services/:name" element={<ServiceDeepDive />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="deployments/:id" element={<DeployDetail />} />
              <Route path="chat" element={<Chat />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
