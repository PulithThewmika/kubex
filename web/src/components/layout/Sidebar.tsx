import { NavLink, useNavigate } from 'react-router-dom'
import { useServices } from '../../hooks/useServices'
import { useAuth } from '../../contexts/AuthContext'

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

function SignOutIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M15 12H4m0 0 3.5-3.5M4 12l3.5 3.5M14 5h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
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
]

const SETTINGS_ITEM: NavItem = { to: '/app/settings', label: 'Settings', icon: SettingsIcon }

// Styled after the landing header's "Sign in with GitHub" CTA — a bordered
// square that's always visible, fills orange when active, inverts to the dark
// surface and lifts on hover.
const navItemClass = ({ isActive }: { isActive: boolean }) =>
  `group relative flex items-center justify-center gap-3 border-2 border-background px-3 py-2.5 font-body text-xs font-bold uppercase tracking-[0.15em] transition-all duration-300 motion-reduce:transform-none lg:justify-start ${
    isActive
      ? 'bg-accent text-background'
      : 'bg-text text-background/60 hover:-translate-y-0.5 hover:scale-[1.03] hover:bg-background hover:text-text'
  }`

function NavRow({ item, badge }: { item: NavItem; badge: number | null }) {
  const { to, label, icon: Icon } = item
  return (
    <NavLink
      to={to}
      end={to === '/app'}
      aria-label={badge ? `${label}, ${badge} active` : label}
      title={label}
      className={navItemClass}
    >
      <span className="relative shrink-0">
        <Icon className="h-5 w-5" />
        {badge && (
          <span
            className="absolute -right-1.5 -top-1.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-failed px-1 text-[10px] font-bold leading-none text-white lg:hidden"
            aria-hidden="true"
          >
            {badge > 9 ? '9+' : badge}
          </span>
        )}
      </span>
      <span className="hidden lg:inline" aria-hidden="true">
        {label}
      </span>
      {badge && (
        <span
          className="ml-auto hidden bg-failed px-1.5 py-0.5 text-xs font-bold tabular-nums text-white lg:inline"
          aria-hidden="true"
        >
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  // Derived from the per-service active_alert_count already on /api/services
  // (the app's primary polled query) rather than fetching the unbounded
  // /api/alerts list on every authenticated page just for a count.
  const { data: services } = useServices()
  const activeAlertCount = services?.reduce((sum, s) => sum + s.active_alert_count, 0) ?? 0
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="flex h-full w-[4.5rem] shrink-0 flex-col border-r-2 border-background bg-text text-background lg:w-60">
      <nav className="flex flex-1 flex-col gap-2 p-2 lg:p-3">
        {NAV_ITEMS.map((item) => (
          <NavRow
            key={item.to}
            item={item}
            badge={item.to === '/app/alerts' && activeAlertCount > 0 ? activeAlertCount : null}
          />
        ))}
        <div className="flex-1" aria-hidden="true" />
        <NavRow item={SETTINGS_ITEM} badge={null} />
        <button
          type="button"
          onClick={handleSignOut}
          title="Sign out"
          className="group relative flex items-center justify-center gap-3 border-2 border-background bg-text px-3 py-2.5 font-body text-xs font-bold uppercase tracking-[0.15em] text-background/60 transition-all duration-300 motion-reduce:transform-none hover:-translate-y-0.5 hover:scale-[1.03] hover:bg-failed hover:text-background lg:justify-start"
        >
          <span className="shrink-0">
            <SignOutIcon className="h-5 w-5" />
          </span>
          <span className="hidden lg:inline">Sign out</span>
        </button>
      </nav>
    </aside>
  )
}
