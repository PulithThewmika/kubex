import type { Cluster } from '../../types/cluster'
import type { Installation } from '../../types/installation'
import type { DeployMethod } from './DeployMethodStep'
import type { MetricsMethod } from './MetricsStep'

const DEPLOY_LABELS: Record<DeployMethod, string> = {
  argocd: 'ArgoCD sync tracking',
  github: 'GitHub deployment statuses',
  webhook: 'Deploy webhook (org API key)',
  skip: 'Not configured yet',
}

const METRICS_LABELS: Record<MetricsMethod, string> = {
  prometheus: 'Prometheus via the KubeX agent',
  healthcheck: 'HTTP health checks',
  skip: 'Not configured yet',
}

function CheckIcon({ muted }: { muted: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={`mt-0.5 h-4 w-4 shrink-0 ${muted ? 'text-text-muted' : 'text-healthy'}`}
      fill="none"
      aria-hidden="true"
    >
      {muted ? (
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.75" />
      ) : (
        <path d="m5 10 3.5 3.5L15 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  )
}

type SummaryRow = { label: string; value: string; done: boolean }

type SummaryStepProps = {
  installations: Installation[] | undefined
  clusters: Cluster[] | undefined
  deployMethod: DeployMethod | null
  metricsMethod: MetricsMethod | null
  onFinish: () => void
  finishing: boolean
  finishError: string | null
}

export function SummaryStep({
  installations,
  clusters,
  deployMethod,
  metricsMethod,
  onFinish,
  finishing,
  finishError,
}: SummaryStepProps) {
  const installCount = installations?.length ?? 0
  const clusterCount = clusters?.length ?? 0

  const rows: SummaryRow[] = [
    {
      label: 'Repositories',
      value: installCount > 0 ? `${installCount} GitHub account${installCount === 1 ? '' : 's'} connected` : 'No GitHub App installed',
      done: installCount > 0,
    },
    {
      label: 'Clusters',
      value: clusterCount > 0 ? `${clusterCount} cluster${clusterCount === 1 ? '' : 's'} connected` : 'No cluster connected',
      done: clusterCount > 0,
    },
    {
      label: 'Deploy source',
      value: deployMethod ? DEPLOY_LABELS[deployMethod] : DEPLOY_LABELS.skip,
      done: !!deployMethod && deployMethod !== 'skip',
    },
    {
      label: 'Metrics',
      value: metricsMethod ? METRICS_LABELS[metricsMethod] : METRICS_LABELS.skip,
      done: !!metricsMethod && metricsMethod !== 'skip',
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-xl font-semibold text-text">You're set</h2>
        <p className="text-sm text-text-muted">
          Here's what's connected. Anything you skipped can be finished later from Settings.
        </p>
      </div>

      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
        {rows.map((row) => (
          <li key={row.label} className="flex items-start gap-3 p-3.5">
            <CheckIcon muted={!row.done} />
            <span className="flex flex-col gap-0.5">
              <span className="text-sm font-medium text-text">{row.label}</span>
              <span className="text-xs text-text-muted">{row.value}</span>
            </span>
          </li>
        ))}
      </ul>

      {finishError && <p className="text-sm text-failed">{finishError}</p>}

      <button
        type="button"
        onClick={onFinish}
        disabled={finishing}
        className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:opacity-50"
      >
        {finishing ? 'Finishing…' : 'Go to Dashboard'}
      </button>
    </div>
  )
}
