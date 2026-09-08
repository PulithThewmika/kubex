type Variant = 'healthy' | 'degraded' | 'failed'

const VARIANT_STYLES: Record<Variant, string> = {
  healthy: 'bg-healthy/10 text-healthy ring-healthy/25',
  degraded: 'bg-degraded/10 text-degraded ring-degraded/25',
  failed: 'bg-failed/10 text-failed ring-failed/25',
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
      className={`inline-flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${VARIANT_STYLES[variant]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[variant]}`} aria-hidden="true" />
      {children}
    </span>
  )
}
