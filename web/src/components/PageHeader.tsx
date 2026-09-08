import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  description?: string
  actions?: ReactNode
}

// One consistent page-title treatment across Overview / Services / Alerts /
// Settings. The <h1> here is the page's real document heading.
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4 border-b-2 border-text pb-5">
      <div>
        <h1 className="font-heading text-2xl font-bold uppercase tracking-tight text-text sm:text-3xl">{title}</h1>
        {description && (
          <p className="mt-1.5 font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
