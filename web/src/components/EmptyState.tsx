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
      className="mx-auto flex max-w-sm flex-col items-center gap-2 px-4 py-12 text-center"
    >
      {icon && <div className="mb-1 text-text-muted">{icon}</div>}
      <h3 className="font-heading text-base font-semibold text-text">{title}</h3>
      {description && <p className="text-sm text-text-muted">{description}</p>}
      {action && (
        <div className="mt-3">
          <ActionButton action={action} />
        </div>
      )}
    </div>
  )
}
