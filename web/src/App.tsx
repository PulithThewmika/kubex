import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './components/auth/RequireAuth'
import { AppLayout } from './components/layout/AppLayout'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { Overview } from './pages/Overview'
import { ServiceDeepDive } from './pages/ServiceDeepDive'
import { DeployDetail } from './pages/DeployDetail'
import { Chat } from './pages/Chat'
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
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return null
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
              <Route index element={<Overview />} />
              <Route path="services" element={<PlaceholderPage title="Services" />} />
              <Route path="services/:name" element={<ServiceDeepDive />} />
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
