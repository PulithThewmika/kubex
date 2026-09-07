import type { ReactNode } from 'react'

type ModalProps = {
  titleId: string
  title: string
  onClose: () => void
  children: ReactNode
  widthClassName?: string
}

export function Modal({ titleId, title, onClose, children, widthClassName = 'max-w-lg' }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`flex max-h-[85vh] w-full ${widthClassName} flex-col overflow-y-auto rounded-lg border border-border bg-surface p-6`}
      >
        <div className="flex items-center justify-between">
          <h2 id={titleId} className="font-heading text-lg font-semibold text-text">
            {title}
          </h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
