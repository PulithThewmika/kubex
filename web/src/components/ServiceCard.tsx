import { formatDistanceToNow } from 'date-fns'
import { ArrowRight } from 'lucide-react'
import { HealthRing } from './HealthRing'
import { ConnectionBadge } from './ConnectionBadge'
import type { Service } from '../types/service'

type ServiceCardProps = {
  service: Service
  index?: number
}

const VERDICT_STYLE: Record<string, string> = {
  healthy: 'border-healthy text-healthy',
  degraded: 'border-degraded text-degraded',
  failed: 'border-failed text-failed',
}

// Poster-style service card. Hover choreography (lift, accent border + offset
// shadow, wipe bar, sliding arrow) is driven entirely from the wrapping
// `.group` Link in ServiceCardGrid — pure CSS, no motion library.
export function ServiceCard({ service, index = 0 }: ServiceCardProps) {
  const {
    name,
    namespace,
    repo,
    latest_deploy,
    health,
    active_alert_count,
    integration_status,
    deploy_count_30d,
  } = service
  const shortSha = latest_deploy?.commit_sha ? latest_deploy.commit_sha.slice(0, 7) : null
  const verdict = health?.verdict ?? null

  return (
    <div className="relative flex h-full flex-col overflow-hidden border-2 border-paper-line-soft bg-paper-raised transition-all duration-300 group-hover:-translate-y-1 group-hover:border-accent group-hover:shadow-[6px_6px_0_0_rgba(255,87,34,0.18)]">
      <span
        aria-hidden="true"
        className="absolute left-0 top-0 z-10 h-1 w-0 bg-accent transition-all duration-300 group-hover:w-full"
      />

      <div className="relative flex items-center justify-between gap-3 border-b-2 border-paper-line-soft bg-paper p-4">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 text-accent/[0.05] halftone-lg" />
        <span className="relative font-display text-3xl leading-none text-paper-line-soft transition-colors group-hover:text-accent/50">
          {String(index + 1).padStart(2, '0')}
        </span>
        <div className="relative flex items-center gap-2">
          {verdict && (
            <span
              className={`border px-1.5 py-0.5 font-body text-[11px] font-bold uppercase tracking-wide ${
                VERDICT_STYLE[verdict] ?? 'border-paper-line-soft text-ink-faint'
              }`}
            >
              {verdict}
            </span>
          )}
          <HealthRing score={health?.score ?? null} verdict={verdict} size={44} />
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-2 font-body text-[11px] font-bold uppercase tracking-[0.15em] text-ink-faint">
          <span className="truncate">{namespace}</span>
          <span className="shrink-0 tabular-nums">{deploy_count_30d}/30d</span>
        </div>

        <div className="flex items-center gap-2">
          <h3 className="truncate font-heading text-lg font-bold uppercase tracking-tight text-ink">{name}</h3>
          {active_alert_count > 0 && (
            <span
              className="flex shrink-0 items-center gap-1 border border-failed px-1.5 py-0.5 font-body text-[11px] font-bold text-failed"
              aria-label={`${active_alert_count} active alert${active_alert_count === 1 ? '' : 's'}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-failed" aria-hidden="true" />
              {active_alert_count}
            </span>
          )}
        </div>

        {repo && <div className="truncate font-mono text-xs text-ink-muted">{repo}</div>}

        <p className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
          {latest_deploy ? (
            <>
              <span className="font-mono normal-case tracking-normal text-ink">
                {shortSha ?? latest_deploy.status}
              </span>{' '}
              by {latest_deploy.author ?? 'unknown'}
              {latest_deploy.finished_at
                ? `, ${formatDistanceToNow(new Date(latest_deploy.finished_at), { addSuffix: true })}`
                : ', in progress'}
            </>
          ) : (
            <span className="text-ink-faint">No deploys yet</span>
          )}
        </p>

        {integration_status && <ConnectionBadge status={integration_status} />}

        <span className="mt-auto inline-flex items-center gap-1.5 pt-1 font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-faint transition-colors group-hover:text-accent">
          Open service
          <ArrowRight
            className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1"
            strokeWidth={2.5}
          />
        </span>
      </div>
    </div>
  )
}
