import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Action =
  | { label: string; to: string; onClick?: never; href?: never }
  | { label: string; href: string; onClick?: never; to?: never }
  | { label: string; onClick: () => void; to?: never; href?: never }

type EmptyStateProps = {
  icon?: ReactNode
  /** Full illustration shown in place of the small icon box. */
  image?: string
  title: string
  description?: string
  action?: Action
}

const ACTION_CLASS =
  'inline-flex items-center border-2 border-accent bg-accent px-4 py-2 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px'

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

export function EmptyState({ icon, image, title, description, action }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={`relative mx-auto flex flex-col items-center gap-2 overflow-hidden border-2 border-paper-line-soft px-4 text-center ${
        image ? 'max-w-xl py-10' : 'max-w-sm py-14'
      }`}
    >
      <div aria-hidden="true" className="absolute inset-0 text-accent/[0.06] halftone-lg" />
      {image ? (
        <img src={image} alt="" className="relative z-10 mb-2 w-full max-w-md select-none object-contain" />
      ) : (
        <div className="relative z-10 mb-2 flex h-11 w-11 items-center justify-center border-2 border-paper-line-soft bg-paper-raised text-ink-muted">
          {icon ?? (
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
              <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.75" />
              <path d="M3 9h18M8 4v16" stroke="currentColor" strokeWidth="1.75" />
            </svg>
          )}
        </div>
      )}
      <h3 className="relative z-10 font-heading text-lg font-bold uppercase tracking-tight text-ink">{title}</h3>
      {description && (
        <p className="relative z-10 font-body text-xs font-semibold uppercase leading-relaxed tracking-wide text-ink-muted">
          {description}
        </p>
      )}
      {action && (
        <div className="relative z-10 mt-3">
          <ActionButton action={action} />
        </div>
      )}
    </div>
  )
}
