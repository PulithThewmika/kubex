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
}

export function MetricsStep({ value, onChange, onAddCluster }: MetricsStepProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-3xl uppercase leading-none text-text sm:text-4xl">Connect your metrics</h2>
        <p className="max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
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
            className="w-fit border-2 border-text-muted px-3.5 py-2 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
          >
            Add a cluster
          </button>
        )}
        {value === 'healthcheck' && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            You'll set a check URL from each service's page once your first deployment lands — there's no
            service to attach one to yet.
          </p>
        )}
      </RadioCards>
    </div>
  )
}
