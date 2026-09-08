import { changePercentColorClass, formatChangePercent } from '../lib/changePercent'
import type { CompareMetric } from '../types/compare'

type DeployDiffTableProps = {
  metrics: CompareMetric[]
}

const METRIC_LABELS: Record<string, string> = {
  error_rate: 'Error rate',
  latency_p99: 'p99 latency',
  restarts: 'Restarts',
}

export function DeployDiffTable({ metrics }: DeployDiffTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface text-left text-xs uppercase tracking-wide text-text-faint">
            <th className="px-3 py-2 font-medium">Metric</th>
            <th className="px-3 py-2 font-medium">Deploy A</th>
            <th className="px-3 py-2 font-medium">Deploy B</th>
            <th className="px-3 py-2 font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.metric} className="border-b border-border last:border-0 hover:bg-surface">
              <td className="px-3 py-2 text-text">{METRIC_LABELS[m.metric] ?? m.metric}</td>
              <td className="px-3 py-2 font-mono text-text-muted">{m.deploy_a ?? '—'}</td>
              <td className="px-3 py-2 font-mono text-text-muted">{m.deploy_b ?? '—'}</td>
              <td className={`px-3 py-2 font-mono font-medium ${changePercentColorClass(m.change_pct)}`}>
                {formatChangePercent(m.change_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
