import { Link } from 'react-router-dom'
import { useServices } from '../../hooks/useServices'

export function HeaderAlertsBell() {
  const { data: services } = useServices()
  const count = services?.reduce((n, s) => n + s.active_alert_count, 0) ?? 0

  return (
    <Link
      to="/app/alerts"
      title="Alerts"
      aria-label={count > 0 ? `Alerts, ${count} active` : 'Alerts'}
      className="relative flex h-8 w-8 items-center justify-center text-background/70 transition-colors hover:text-background"
    >
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
        <path
          d="M12 3a6 6 0 0 0-6 6c0 3.6-1.2 5.4-2 6.3-.4.5-.1 1.2.5 1.2h15c.6 0 .9-.7.5-1.2-.8-.9-2-2.7-2-6.3a6 6 0 0 0-6-6Z"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinejoin="round"
        />
        <path d="M10 20a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      </svg>
      {count > 0 && (
        <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-failed px-1 text-[10px] font-bold leading-none text-white ring-2 ring-text">
          {count > 9 ? '9+' : count}
        </span>
      )}
    </Link>
  )
}
