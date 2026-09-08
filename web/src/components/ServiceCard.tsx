import { formatDistanceToNow } from 'date-fns'
import { HealthRing } from './HealthRing'
import { ConnectionBadge } from './ConnectionBadge'
import type { Service } from '../types/service'

type ServiceCardProps = {
  service: Service
}

export function ServiceCard({ service }: ServiceCardProps) {
  const { name, namespace, latest_deploy, health, active_alert_count, integration_status } = service
  const shortSha = latest_deploy?.commit_sha ? latest_deploy.commit_sha.slice(0, 7) : null

  return (
    <div className="flex h-full flex-col gap-3 border-2 border-border-strong bg-surface p-4 transition-colors hover:border-accent">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="truncate font-heading text-base font-bold uppercase tracking-tight text-text">
              {name}
            </span>
            {active_alert_count > 0 && (
              <span
                className="flex items-center gap-1 border border-failed px-1.5 py-0.5 font-body text-[11px] font-bold text-failed"
                aria-label={`${active_alert_count} active alert${active_alert_count === 1 ? '' : 's'}`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-failed" aria-hidden="true" />
                {active_alert_count}
              </span>
            )}
          </div>
          <span className="w-fit border border-border-strong bg-background px-1.5 py-0.5 font-mono text-[11px] text-text-muted">
            {namespace}
          </span>
        </div>
        <HealthRing score={health?.score ?? null} verdict={health?.verdict ?? null} size={48} />
      </div>

      <div className="mt-auto font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
        {latest_deploy ? (
          <span>
            <span className="font-mono normal-case tracking-normal text-text">
              {shortSha ?? latest_deploy.status}
            </span>{' '}
            by {latest_deploy.author ?? 'unknown'}
            {latest_deploy.finished_at
              ? `, ${formatDistanceToNow(new Date(latest_deploy.finished_at), { addSuffix: true })}`
              : ', in progress'}
          </span>
        ) : (
          <span className="text-text-faint">No deploys yet</span>
        )}
      </div>

      {integration_status && <ConnectionBadge status={integration_status} />}
    </div>
  )
}
