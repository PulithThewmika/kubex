import type { IntegrationStatus } from '../types/service'

const CD_LABELS: Record<string, string> = {
  argocd: 'ArgoCD',
  github_deployments: 'GitHub Deployments',
  webhook: 'Webhook',
}

const METRICS_LABELS: Record<string, string> = {
  prometheus: 'Prometheus',
  health_check: 'Health check',
}

type Tier = {
  key: string
  label: string
  connected: boolean
  detail: string
}

function Pill({ label, connected, detail }: Omit<Tier, 'key'>) {
  return (
    <span
      className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-body text-[11px] font-bold uppercase tracking-wide ${
        connected ? 'border-healthy bg-healthy/10 text-healthy' : 'border-border-strong bg-surface-raised text-text-faint'
      }`}
      title={`${label}: ${detail}`}
      aria-label={`${label}: ${detail}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-healthy' : 'bg-text-faint'}`}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

export function ConnectionBadge({ status }: { status: IntegrationStatus }) {
  const tiers: Tier[] = [
    {
      key: 'ci',
      label: 'CI',
      connected: status.ci,
      detail: status.ci ? 'connected' : 'not connected',
    },
    {
      key: 'cd',
      label: 'CD',
      connected: status.cd !== null,
      detail: status.cd ? CD_LABELS[status.cd] ?? status.cd : 'not connected',
    },
    {
      key: 'metrics',
      label: 'Metrics',
      connected: status.metrics !== null,
      detail: status.metrics ? METRICS_LABELS[status.metrics] ?? status.metrics : 'not connected',
    },
  ]

  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Integration status">
      {tiers.map(({ key, ...rest }) => (
        <Pill key={key} {...rest} />
      ))}
    </div>
  )
}
