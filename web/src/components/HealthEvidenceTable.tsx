import { changePercentColorClass, formatChangePercent } from '../lib/changePercent'
import type { HealthEvidenceItem } from '../types/deploymentDetail'

type HealthEvidenceTableProps = {
  evidence: HealthEvidenceItem[]
}

const METRIC_LABELS: Record<string, string> = {
  error_rate: 'Error rate',
  latency_p99: 'p99 latency',
  restarts: 'Restarts',
}

export function HealthEvidenceTable({ evidence }: HealthEvidenceTableProps) {
  return (
    <div className="overflow-x-auto border-2 border-paper-line-soft">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-2 border-paper-line-soft bg-paper text-left font-body text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="px-3 py-2 font-bold">Metric</th>
            <th className="px-3 py-2 font-bold">Baseline</th>
            <th className="px-3 py-2 font-bold">Post-deploy</th>
            <th className="px-3 py-2 font-bold">Change</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((item) => (
            <tr key={item.metric} className="border-b border-paper-line-soft last:border-0 hover:bg-paper">
              <td className="px-3 py-2 text-ink">{METRIC_LABELS[item.metric] ?? item.metric}</td>
              <td className="px-3 py-2 font-mono text-ink-muted">{item.baseline ?? '—'}</td>
              <td className="px-3 py-2 font-mono text-ink-muted">{item.post ?? '—'}</td>
              <td className={`px-3 py-2 font-mono font-medium ${changePercentColorClass(item.change_pct)}`}>
                {formatChangePercent(item.change_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
