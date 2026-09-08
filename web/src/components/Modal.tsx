import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

type ModalProps = {
  titleId: string
  title: string
  onClose: () => void
  children: ReactNode
  widthClassName?: string
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Modal({ titleId, title, onClose, children, widthClassName = 'max-w-lg' }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    // Restore focus to whatever triggered the modal once it closes — without
    // this, focus silently drops to <body> and keyboard users lose their
    // place in the page (CodeRabbit, PR #804).
    const previouslyFocused = document.activeElement as HTMLElement | null

    // Nothing inside autofocuses in every step (AddClusterModal's first step
    // does; its later steps and RotateTokenDialog don't) — move focus into
    // the dialog itself as a baseline so Escape/Tab work immediately either way.
    if (!panelRef.current?.contains(document.activeElement)) {
      panelRef.current?.focus()
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab' || !panelRef.current) return
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      // Basic focus trap: wrap Tab/Shift+Tab at the dialog's edges instead
      // of letting it escape to background page controls. The panel itself
      // (tabIndex=-1) counts as the "first" boundary too — it's what's
      // actually focused right after mount on any step that doesn't
      // autofocus a real control (CodeRabbit, PR #804).
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previouslyFocused?.focus()
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`flex max-h-[85vh] w-full ${widthClassName} animate-fade-in flex-col overflow-y-auto border-2 border-paper-line bg-paper-raised p-6 outline-none sm:p-8`}
      >
        <div className="flex items-center justify-between border-b-2 border-paper-line pb-4">
          <h2 id={titleId} className="font-display text-2xl uppercase leading-none text-ink">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 -mt-1 border-2 border-transparent p-1.5 text-ink-muted transition-colors hover:border-accent hover:text-accent"
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
