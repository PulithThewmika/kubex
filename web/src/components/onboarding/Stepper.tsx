type StepperProps = {
  steps: string[]
  /** Zero-based index of the active step. */
  current: number
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
      <path d="m5 10 3.5 3.5L15 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// Step indicator shown at the top of the onboarding wizard. Steps are
// navigated (not scroll-revealed), so this is plain state-driven markup —
// no Reveal / IntersectionObserver.
export function Stepper({ steps, current }: StepperProps) {
  return (
    <ol className="flex items-center" aria-label="Setup progress">
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <li key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2.5">
              <span
                aria-current={active ? 'step' : undefined}
                className={`flex h-8 w-8 shrink-0 items-center justify-center border-2 font-display text-sm transition-colors ${
                  done
                    ? 'border-accent bg-accent text-background'
                    : active
                      ? 'border-accent text-accent'
                      : 'border-border-strong text-text-muted'
                }`}
              >
                {done ? <CheckIcon /> : i + 1}
              </span>
              <span
                className={`hidden font-body text-xs font-bold uppercase tracking-[0.15em] sm:inline ${active ? 'text-text' : 'text-text-muted'}`}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <span className={`mx-3 h-0.5 flex-1 ${done ? 'bg-accent' : 'bg-border-strong'}`} aria-hidden="true" />
            )}
          </li>
        )
      })}
    </ol>
  )
}
