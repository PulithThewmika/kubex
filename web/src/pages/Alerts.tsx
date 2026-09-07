import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { formatDistanceStrict, formatDistanceToNow } from 'date-fns'
import { AlertSeverityBadge } from '../components/AlertSeverityBadge'
import { EmptyState } from '../components/EmptyState'
import { useAlerts } from '../hooks/useAlerts'
import type { Alert } from '../types/alert'

const FILTERS = [
  { id: 'active', label: 'Active' },
  { id: 'resolved', label: 'Resolved' },
  { id: 'all', label: 'All' },
] as const

type FilterId = (typeof FILTERS)[number]['id']

function isFilterId(value: string | null): value is FilterId {
  return value !== null && FILTERS.some((f) => f.id === value)
}

function AlertRow({ alert }: { alert: Alert }) {
  const resolved = alert.resolved_at !== null
  return (
    <li className="flex flex-col gap-2 border-b border-border px-4 py-3 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex items-center gap-3 sm:w-40 sm:shrink-0">
        <AlertSeverityBadge severity={alert.severity} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-text">{alert.title}</p>
        {alert.description && (
          <p className="truncate text-xs text-text-muted">{alert.description}</p>
        )}
      </div>
      <div className="text-xs text-text-muted sm:w-32 sm:shrink-0">
        <span className="rounded border border-border px-1.5 py-0.5">{alert.service_name}</span>
      </div>
      <Link
        to={`/app/deployments/${alert.deployment_id}`}
        className="text-xs font-medium text-accent hover:underline sm:w-24 sm:shrink-0"
      >
        Deployment #{alert.deployment_id}
      </Link>
      <div className="text-xs text-text-muted sm:w-44 sm:shrink-0 sm:text-right">
        {resolved ? (
          <span>
            Resolved in{' '}
            {formatDistanceStrict(new Date(alert.resolved_at as string), new Date(alert.fired_at))}
          </span>
        ) : (
          <span>Fired {formatDistanceToNow(new Date(alert.fired_at), { addSuffix: true })}</span>
        )}
      </div>
    </li>
  )
}

export function Alerts() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filterParam = searchParams.get('status')
  const activeFilter: FilterId = isFilterId(filterParam) ? filterParam : 'active'

  const { data: alerts, isLoading, isError } = useAlerts()

  const visible = useMemo(() => {
    if (!alerts) return []
    if (activeFilter === 'active') return alerts.filter((a) => a.resolved_at === null)
    if (activeFilter === 'resolved') return alerts.filter((a) => a.resolved_at !== null)
    return alerts
  }, [alerts, activeFilter])

  const activeCount = alerts?.filter((a) => a.resolved_at === null).length ?? 0

  function selectFilter(id: FilterId) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('status', id)
        return next
      },
      { replace: true },
    )
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="font-heading text-xl font-semibold text-text">Alerts</h1>
        {activeCount > 0 && (
          <span className="rounded-full bg-failed/10 px-2 py-0.5 text-xs font-medium text-failed">
            {activeCount} active
          </span>
        )}
      </div>

      <div role="tablist" aria-label="Alert status filter" className="mb-4 flex gap-1">
        {FILTERS.map((f) => {
          const selected = f.id === activeFilter
          return (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => selectFilter(f.id)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                selected
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-muted hover:bg-surface hover:text-text'
              }`}
            >
              {f.label}
            </button>
          )
        })}
      </div>

      {isError ? (
        <p className="text-sm text-failed">Failed to load alerts. Retrying automatically.</p>
      ) : isLoading ? (
        <ul className="overflow-hidden rounded-lg border border-border bg-surface" aria-busy="true">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="border-b border-border px-4 py-4 last:border-b-0">
              <div className="h-4 w-3/4 animate-pulse rounded bg-border" />
            </li>
          ))}
        </ul>
      ) : visible.length === 0 ? (
        <EmptyState
          title={activeFilter === 'active' ? 'All clear' : 'Nothing here'}
          description={
            activeFilter === 'active'
              ? 'No active alerts. Every service is within its health thresholds.'
              : activeFilter === 'resolved'
                ? 'No resolved alerts yet.'
                : 'No alerts have been recorded yet.'
          }
        />
      ) : (
        <ul className="overflow-hidden rounded-lg border border-border bg-surface">
          {visible.map((alert) => (
            <AlertRow key={alert.id} alert={alert} />
          ))}
        </ul>
      )}
    </div>
  )
}
