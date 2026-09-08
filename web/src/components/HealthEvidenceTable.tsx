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
    <div className="overflow-x-auto border-2 border-border-strong">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-2 border-border-strong bg-surface text-left font-body text-[11px] uppercase tracking-wide text-text-faint">
            <th className="px-3 py-2 font-bold">Metric</th>
            <th className="px-3 py-2 font-bold">Baseline</th>
            <th className="px-3 py-2 font-bold">Post-deploy</th>
            <th className="px-3 py-2 font-bold">Change</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((item) => (
            <tr key={item.metric} className="border-b border-border-strong last:border-0 hover:bg-surface">
              <td className="px-3 py-2 text-text">{METRIC_LABELS[item.metric] ?? item.metric}</td>
              <td className="px-3 py-2 font-mono text-text-muted">{item.baseline ?? '—'}</td>
              <td className="px-3 py-2 font-mono text-text-muted">{item.post ?? '—'}</td>
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
