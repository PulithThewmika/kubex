import { Outlet, useLocation } from 'react-router-dom'
import { ErrorBoundary } from '../ErrorBoundary'
import { WelcomeTour } from '../onboarding/WelcomeTour'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppLayout() {
  const location = useLocation()
  return (
    <div className="flex h-dvh bg-background text-text">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="relative flex-1 overflow-y-auto bg-paper text-ink">
          <div aria-hidden="true" className="pointer-events-none fixed inset-0 text-paper-line/[0.04] halftone-lg" />
          <div key={location.pathname} className="relative mx-auto max-w-7xl animate-page-in">
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <WelcomeTour />
    </div>
  )
}
