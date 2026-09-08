import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { formatDistanceStrict, formatDistanceToNow } from 'date-fns'
import { AlertSeverityBadge } from '../components/AlertSeverityBadge'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
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
    <li className="flex flex-col gap-2 border-b-2 border-paper-line-soft px-4 py-2.5 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex items-center gap-3 sm:w-40 sm:shrink-0">
        <AlertSeverityBadge severity={alert.severity} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-body text-sm font-bold text-ink">{alert.title}</p>
        {alert.description && (
          <p className="truncate font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
            {alert.description}
          </p>
        )}
      </div>
      <div className="text-xs text-ink-muted sm:w-32 sm:shrink-0">
        <span className="border border-paper-line-soft bg-paper px-1.5 py-0.5 font-mono">
          {alert.service_name}
        </span>
      </div>
      <Link
        to={`/app/deployments/${alert.deployment_id}`}
        className="font-body text-xs font-bold uppercase tracking-wide text-accent hover:underline sm:w-24 sm:shrink-0"
      >
        Deployment #{alert.deployment_id}
      </Link>
      <div className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted sm:w-44 sm:shrink-0 sm:text-right">
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
      <PageHeader
        title="Alerts"
        actions={
          activeCount > 0 ? (
            <span className="border-2 border-failed bg-failed/10 px-2 py-0.5 font-body text-xs font-bold uppercase tabular-nums tracking-wide text-failed">
              {activeCount} active
            </span>
          ) : undefined
        }
      />

      <div
        role="tablist"
        aria-label="Alert status filter"
        className="mb-5 inline-flex gap-1 border-2 border-paper-line-soft bg-paper-raised p-1"
      >
        {FILTERS.map((f) => {
          const selected = f.id === activeFilter
          return (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => selectFilter(f.id)}
              className={`px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide transition-colors ${
                selected
                  ? 'bg-accent text-background'
                  : 'text-ink-muted hover:bg-paper hover:text-ink'
              }`}
            >
              {f.label}
            </button>
          )
        })}
      </div>

      {isError ? (
        <div className="border-2 border-failed bg-failed/5 p-4 font-body text-xs font-bold uppercase tracking-wide text-failed">
          Failed to load alerts. Retrying automatically.
        </div>
      ) : isLoading ? (
        <ul className="overflow-hidden border-2 border-paper-line-soft bg-paper-raised" aria-busy="true">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="border-b-2 border-paper-line-soft px-4 py-3 last:border-b-0">
              <div className="h-4 w-3/4 animate-pulse bg-paper-line-soft" />
            </li>
          ))}
        </ul>
      ) : visible.length === 0 ? (
        activeFilter === 'active' ? (
          <div
            role="status"
            className="flex flex-col items-center gap-4 border-2 border-paper-line-soft bg-paper-raised px-4 py-10 text-center"
          >
            <img
              src="/Noalerts.png"
              alt=""
              className="w-full max-w-xl select-none object-contain"
            />
            <h2 className="font-heading text-xl font-bold uppercase tracking-tight text-ink sm:text-2xl">All clear</h2>
            <p className="max-w-md font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
              No active alerts. Every service is within its health thresholds.
            </p>
          </div>
        ) : (
          <EmptyState
            title="Nothing here"
            description={
              activeFilter === 'resolved' ? 'No resolved alerts yet.' : 'No alerts have been recorded yet.'
            }
          />
        )
      ) : (
        <ul className="overflow-hidden border-2 border-paper-line-soft bg-paper-raised">
          {visible.map((alert) => (
            <AlertRow key={alert.id} alert={alert} />
          ))}
        </ul>
      )}
    </div>
  )
}
