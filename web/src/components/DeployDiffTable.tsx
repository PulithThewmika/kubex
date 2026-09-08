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
    <div className="overflow-x-auto border-2 border-paper-line-soft">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-2 border-paper-line-soft bg-paper text-left font-body text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="px-3 py-2 font-bold">Metric</th>
            <th className="px-3 py-2 font-bold">Deploy A</th>
            <th className="px-3 py-2 font-bold">Deploy B</th>
            <th className="px-3 py-2 font-bold">Change</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.metric} className="border-b border-paper-line-soft last:border-0 hover:bg-paper">
              <td className="px-3 py-2 text-ink">{METRIC_LABELS[m.metric] ?? m.metric}</td>
              <td className="px-3 py-2 font-mono text-ink-muted">{m.deploy_a ?? '—'}</td>
              <td className="px-3 py-2 font-mono text-ink-muted">{m.deploy_b ?? '—'}</td>
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
