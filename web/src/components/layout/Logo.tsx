type LogoProps = {
  /** Show the "KubeX" wordmark next to the mark. */
  withWordmark?: boolean
  className?: string
  markClassName?: string
}

// The mark is a monochrome steel cube (K/U/B/E) on transparent — it sits on
// any dark surface without a plate.
export function Logo({ withWordmark = true, className = '', markClassName = 'h-7 w-7' }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <img src="/kubex-logo.png" alt="" aria-hidden="true" className={`${markClassName} select-none`} />
      {withWordmark && (
        <span className="font-heading text-lg font-semibold tracking-tight text-text">KubeX</span>
      )}
    </span>
  )
}
