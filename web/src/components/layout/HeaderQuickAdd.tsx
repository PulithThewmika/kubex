import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnClickOutside } from '../../hooks/useOnClickOutside'
import { QUICK_ADD_ACTIONS } from './headerActions'

export function HeaderQuickAdd() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useOnClickOutside(ref, () => setOpen(false))

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Quick add"
        className="flex h-8 w-8 items-center justify-center border-2 border-background/20 text-background/70 transition-colors hover:border-accent hover:text-accent"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
          <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-11 z-30 w-60 origin-top-right animate-fade-in border-2 border-paper-line bg-paper-raised text-ink shadow-[4px_4px_0_0_rgba(22,23,26,0.15)]"
        >
          <p className="border-b-2 border-paper-line-soft px-3 py-2 font-body text-[10px] font-bold uppercase tracking-[0.2em] text-ink-faint">
            Add
          </p>
          {QUICK_ADD_ACTIONS.map((a) => (
            <button
              key={a.label}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                navigate(a.to)
              }}
              className="flex w-full items-center gap-2 border-b-2 border-paper-line-soft px-3 py-2.5 text-left font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-muted transition-colors last:border-b-0 hover:bg-accent hover:text-background"
            >
              <span aria-hidden="true">＋</span>
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
