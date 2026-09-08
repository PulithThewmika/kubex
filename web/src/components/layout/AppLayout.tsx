import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AgentFab } from '../AgentFab'
import { ErrorBoundary } from '../ErrorBoundary'
import { WelcomeTour } from '../onboarding/WelcomeTour'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

// ponytail: per-browser localStorage flag, no cross-device sync needed for a
// layout preference.
const SIDEBAR_KEY = 'kubex.sidebar.hidden'

function readSidebarHidden(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === '1'
  } catch {
    return false
  }
}

export function AppLayout() {
  const location = useLocation()
  const [sidebarHidden, setSidebarHidden] = useState(readSidebarHidden)

  function toggleSidebar() {
    setSidebarHidden((hidden) => {
      const next = !hidden
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0')
      } catch {
        // storage disabled — the toggle still works for this session
      }
      return next
    })
  }

  return (
    <div className="flex h-dvh flex-col bg-background text-text">
      <TopBar sidebarHidden={sidebarHidden} onToggleSidebar={toggleSidebar} />
      <div className="flex min-h-0 flex-1">
        {!sidebarHidden && <Sidebar />}
        <main className="relative min-w-0 flex-1 overflow-y-auto bg-paper text-ink">
          <div aria-hidden="true" className="pointer-events-none fixed inset-0 text-paper-line/[0.04] halftone-lg" />
          <div key={location.pathname} className="relative mx-auto max-w-7xl animate-page-in">
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <WelcomeTour />
      <AgentFab />
    </div>
  )
}
