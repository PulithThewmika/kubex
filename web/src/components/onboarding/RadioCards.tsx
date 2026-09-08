import type { ReactNode } from 'react'

export type RadioOption = {
  value: string
  label: string
  description: string
}

type RadioCardsProps = {
  /** Accessible name for the group — visually hidden, since each step
   *  already renders a visible heading. */
  legend: string
  name: string
  options: RadioOption[]
  value: string | null
  onChange: (value: string) => void
  /** Extra content rendered under the selected option (e.g. an inline
   *  action button or a URL field). */
  children?: ReactNode
}

export function RadioCards({ legend, name, options, value, onChange, children }: RadioCardsProps) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="sr-only">{legend}</legend>
      {options.map((opt) => {
        const selected = value === opt.value
        return (
          <div key={opt.value}>
            <label
              className={`flex cursor-pointer gap-4 border-2 p-4 transition-colors ${
                selected ? 'border-accent bg-accent/10' : 'border-paper-line-soft hover:border-ink'
              }`}
            >
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={selected}
                onChange={() => onChange(opt.value)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
              />
              <span className="flex flex-col gap-1">
                <span className="font-display text-base uppercase leading-none text-ink">{opt.label}</span>
                <span className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  {opt.description}
                </span>
              </span>
            </label>
            {selected && children && <div className="mt-2 pl-8">{children}</div>}
          </div>
        )
      })}
    </fieldset>
  )
}
