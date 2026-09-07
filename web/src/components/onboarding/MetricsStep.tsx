import { RadioCards, type RadioOption } from './RadioCards'

export type MetricsMethod = 'prometheus' | 'healthcheck' | 'skip'

const OPTIONS: RadioOption[] = [
  { value: 'prometheus', label: 'Prometheus (via the KubeX agent)', description: 'The cluster agent reads your in-cluster Prometheus — best signal for health scoring.' },
  { value: 'healthcheck', label: 'HTTP health checks', description: 'No Prometheus? KubeX polls a health endpoint per service instead.' },
  { value: 'skip', label: 'Skip for now', description: 'Deployments still get tracked; health scoring stays limited until metrics are connected.' },
]

type MetricsStepProps = {
  value: MetricsMethod | null
  onChange: (value: MetricsMethod) => void
  onAddCluster: () => void
  healthCheckUrl: string
  onHealthCheckUrlChange: (url: string) => void
}

export function MetricsStep({ value, onChange, onAddCluster, healthCheckUrl, onHealthCheckUrlChange }: MetricsStepProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-xl font-semibold text-text">Connect your metrics</h2>
        <p className="text-sm text-text-muted">
          KubeX scores each deployment by comparing error rate, latency and restarts before and after. That
          needs a metrics source.
        </p>
      </div>

      <RadioCards
        legend="Metrics source"
        name="metrics-method"
        options={OPTIONS}
        value={value}
        onChange={(v) => onChange(v as MetricsMethod)}
      >
        {value === 'prometheus' && (
          <button
            type="button"
            onClick={onAddCluster}
            className="w-fit rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-surface"
          >
            Add a cluster
          </button>
        )}
        {value === 'healthcheck' && (
          <label className="flex flex-col gap-1.5 text-xs">
            <span className="font-medium text-text">Health check URL (optional)</span>
            <input
              type="url"
              inputMode="url"
              value={healthCheckUrl}
              onChange={(e) => onHealthCheckUrlChange(e.target.value)}
              placeholder="https://my-service.example.com/healthz"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
            />
            <span className="text-text-muted">
              You'll assign a check URL per service once your first deployment lands — this is just a note for
              now.
            </span>
          </label>
        )}
      </RadioCards>
    </div>
  )
}
