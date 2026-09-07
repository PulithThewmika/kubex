import { NavLink } from 'react-router-dom'
import { useAlerts } from '../../hooks/useAlerts'

type NavItem = {
  to: string
  label: string
  icon: (props: { className?: string }) => JSX.Element
}

function OverviewIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.75" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.75" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.75" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  )
}

function ServicesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  )
}

function AlertsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M12 3a6 6 0 0 0-6 6c0 3.6-1.2 5.4-2 6.3-.4.5-.1 1.2.5 1.2h15c.6 0 .9-.7.5-1.2-.8-.9-2-2.7-2-6.3a6 6 0 0 0-6-6Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path d="M10 20a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  )
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9A1.5 1.5 0 0 1 18.5 16H9l-4 4v-4H5.5A1.5 1.5 0 0 1 4 14.5v-9Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const NAV_ITEMS: NavItem[] = [
  { to: '/app', label: 'Overview', icon: OverviewIcon },
  { to: '/app/services', label: 'Services', icon: ServicesIcon },
  { to: '/app/alerts', label: 'Alerts', icon: AlertsIcon },
  { to: '/app/chat', label: 'Chat', icon: ChatIcon },
  { to: '/app/settings', label: 'Settings', icon: SettingsIcon },
]

export function Sidebar() {
  const { data: alerts } = useAlerts()
  const activeAlertCount = alerts?.filter((a) => a.resolved_at === null).length ?? 0

  return (
    <aside className="flex h-dvh w-16 shrink-0 flex-col border-r border-border bg-surface md:w-56">
      <nav className="flex flex-col gap-1 p-2 md:p-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const badge = to === '/app/alerts' && activeAlertCount > 0 ? activeAlertCount : null
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/app'}
              aria-label={badge ? `${label}, ${badge} active` : label}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-muted hover:bg-background hover:text-text'
                }`
              }
            >
              <span className="relative shrink-0">
                <Icon className="h-5 w-5" />
                {badge && (
                  <span
                    className="absolute -right-1.5 -top-1.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-failed px-1 text-[10px] font-semibold leading-none text-white md:hidden"
                    aria-hidden="true"
                  >
                    {badge > 9 ? '9+' : badge}
                  </span>
                )}
              </span>
              <span className="hidden md:inline" aria-hidden="true">
                {label}
              </span>
              {badge && (
                <span
                  className="ml-auto hidden rounded-full bg-failed/15 px-1.5 py-0.5 text-xs font-semibold text-failed md:inline"
                  aria-hidden="true"
                >
                  {badge > 99 ? '99+' : badge}
                </span>
              )}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
