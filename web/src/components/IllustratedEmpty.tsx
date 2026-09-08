import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type IllustratedEmptyProps = {
  /** Bare illustration — no frame, no background. */
  image: string
  title: string
  /** Instruction rows, stacked as a vertical bordered table. */
  lines: ReactNode[]
  action?: { to: string; label: string }
}

// Centered empty state: a bare PNG beside a vertical bordered "table" of copy,
// sized like the landing "How it works" cells. Shared by the empty services
// and empty alerts states.
export function IllustratedEmpty({ image, title, lines, action }: IllustratedEmptyProps) {
  return (
    <div
      role="status"
      className="mx-auto flex max-w-4xl flex-col items-center gap-8 py-10 md:flex-row md:justify-center md:gap-12 md:py-16"
    >
      <img
        src={image}
        alt=""
        className="w-full max-w-xs shrink-0 select-none object-contain md:max-w-sm"
      />

      <div className="grid w-full gap-px border-2 border-paper-line bg-paper-line md:max-w-md">
        <div className="bg-paper-raised p-6">
          <h2 className="font-display text-3xl uppercase leading-none text-ink sm:text-4xl">{title}</h2>
        </div>
        {lines.map((line, i) => (
          <div key={i} className="bg-paper-raised p-6 font-body text-sm leading-relaxed text-ink-muted">
            {line}
          </div>
        ))}
        {action && (
          <div className="bg-paper-raised p-6">
            <Link
              to={action.to}
              className="inline-block border-2 border-accent bg-accent px-5 py-2.5 font-display text-xl uppercase tracking-wide text-background transition-transform hover:-translate-y-0.5"
            >
              {action.label} →
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
