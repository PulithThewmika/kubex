type Variant = 'healthy' | 'degraded' | 'failed'

const VARIANT_STYLES: Record<Variant, string> = {
  healthy: 'bg-healthy/10 text-healthy',
  degraded: 'bg-degraded/10 text-degraded',
  failed: 'bg-failed/10 text-failed',
}

type StatusBadgeProps = {
  variant: Variant
  children: string
}

export function StatusBadge({ variant, children }: StatusBadgeProps) {
  return (
    <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-medium capitalize ${VARIANT_STYLES[variant]}`}>
      {children}
    </span>
  )
}
