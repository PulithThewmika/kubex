import type { AlertSeverity } from '../types/alert'

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  critical: 'border-failed bg-failed/10 text-failed',
  warning: 'border-degraded bg-degraded/10 text-degraded',
}

const SEVERITY_DOT: Record<AlertSeverity, string> = {
  critical: 'bg-failed',
  warning: 'bg-degraded',
}

export function AlertSeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span
      className={`inline-flex w-fit items-center gap-1.5 border px-2 py-0.5 font-body text-xs font-bold uppercase tracking-wide ${SEVERITY_STYLES[severity]}`}
      aria-label={`Severity: ${severity}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[severity]}`} aria-hidden="true" />
      {severity}
    </span>
  )
}
