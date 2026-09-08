import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Action =
  | { label: string; to: string; onClick?: never; href?: never }
  | { label: string; href: string; onClick?: never; to?: never }
  | { label: string; onClick: () => void; to?: never; href?: never }

type EmptyStateProps = {
  icon?: ReactNode
  title: string
  description?: string
  action?: Action
}

const ACTION_CLASS =
  'inline-flex items-center rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-background transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'

function ActionButton({ action }: { action: Action }) {
  if ('to' in action && action.to !== undefined) {
    return (
      <Link to={action.to} className={ACTION_CLASS}>
        {action.label}
      </Link>
    )
  }
  if ('href' in action && action.href !== undefined) {
    return (
      <a href={action.href} className={ACTION_CLASS} target="_blank" rel="noreferrer">
        {action.label}
      </a>
    )
  }
  return (
    <button type="button" onClick={action.onClick} className={ACTION_CLASS}>
      {action.label}
    </button>
  )
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      role="status"
      className="mx-auto flex max-w-sm flex-col items-center gap-2 rounded-xl border border-dashed border-border px-4 py-14 text-center"
    >
      <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-text-muted">
        {icon ?? (
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.75" />
            <path d="M3 9h18M8 4v16" stroke="currentColor" strokeWidth="1.75" />
          </svg>
        )}
      </div>
      <h3 className="font-heading text-base font-semibold text-text">{title}</h3>
      {description && <p className="text-sm leading-relaxed text-text-muted">{description}</p>}
      {action && (
        <div className="mt-3">
          <ActionButton action={action} />
        </div>
      )}
    </div>
  )
}
