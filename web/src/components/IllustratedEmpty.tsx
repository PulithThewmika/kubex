import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type IllustratedEmptyProps = {
  /** Bare illustration — no frame, no background. */
  image: string
  title: string
  /** Instruction rows, stacked as a vertical bordered table. */
  lines: ReactNode[]
  action?: { to: string; label: string }
  /**
   * 'center' (default) — the pair sits centred in the content area.
   * 'split' — pulled up under the header, picture pushed left, copy pushed right.
   * 'showcase' — centred, dropped down the page, with a larger illustration.
   */
  variant?: 'center' | 'split' | 'showcase'
}

const LAYOUT = {
  center: {
    wrap: 'mx-auto flex max-w-4xl flex-col items-center gap-8 pb-10 pt-2 md:flex-row md:justify-center md:gap-20 md:pb-14 md:pt-4',
    image: 'w-full max-w-xs shrink-0 select-none object-contain md:-ml-20 md:max-w-sm',
    table: 'grid w-full gap-px border-2 border-paper-line bg-paper-line md:ml-6 md:max-w-md',
  },
  split: {
    wrap: 'mx-auto -mt-6 flex max-w-4xl flex-col items-center gap-8 pb-10 pt-0 md:-mt-12 md:flex-row md:justify-center md:gap-24 md:pb-14',
    image: 'w-full max-w-xs shrink-0 select-none object-contain md:-ml-24 md:max-w-sm',
    table: 'grid w-full gap-px border-2 border-paper-line bg-paper-line md:ml-8 md:max-w-md',
  },
  showcase: {
    wrap: 'mx-auto flex max-w-4xl flex-col items-center gap-10 pb-16 pt-12 md:flex-row md:justify-center md:gap-16 md:pb-20 md:pt-20',
    image: 'w-full max-w-sm shrink-0 select-none object-contain md:max-w-md',
    table: 'grid w-full gap-px border-2 border-paper-line bg-paper-line md:max-w-md',
  },
} as const

// A bare PNG beside a vertical bordered "table" of copy, sized like the landing
// "How it works" cells. Shared by the empty services and empty alerts states.
export function IllustratedEmpty({ image, title, lines, action, variant = 'center' }: IllustratedEmptyProps) {
  const l = LAYOUT[variant]
  return (
    <div role="status" className={l.wrap}>
      <img src={image} alt="" className={l.image} />

      <div className={l.table}>
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
