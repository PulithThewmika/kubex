type Variant = 'healthy' | 'degraded' | 'failed'

const VARIANT_STYLES: Record<Variant, string> = {
  healthy: 'border-healthy bg-healthy/10 text-healthy',
  degraded: 'border-degraded bg-degraded/10 text-degraded',
  failed: 'border-failed bg-failed/10 text-failed',
}

const DOT: Record<Variant, string> = {
  healthy: 'bg-healthy',
  degraded: 'bg-degraded',
  failed: 'bg-failed',
}

type StatusBadgeProps = {
  variant: Variant
  children: string
}

export function StatusBadge({ variant, children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex w-fit items-center gap-1.5 border px-2 py-0.5 font-body text-xs font-bold uppercase tracking-wide ${VARIANT_STYLES[variant]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[variant]}`} aria-hidden="true" />
      {children}
    </span>
  )
}
