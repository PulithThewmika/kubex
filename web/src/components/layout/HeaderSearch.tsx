import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useServices } from '../../hooks/useServices'
import { NAV_PAGES, QUICK_ADD_ACTIONS } from './headerActions'

type Item = { group: string; label: string; sub?: string; to: string }

function CommandPalette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const { data: services } = useServices()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase()
    const match = (s: string) => !q || s.toLowerCase().includes(q)

    const svc: Item[] = (services ?? [])
      .filter((s) => match(s.name) || match(s.namespace))
      .slice(0, 6)
      .map((s) => ({ group: 'Services', label: s.name, sub: s.namespace, to: `/app/services/${s.name}` }))
    const actions: Item[] = QUICK_ADD_ACTIONS.filter((a) => match(a.label)).map((a) => ({
      group: 'Actions',
      ...a,
    }))
    const pages: Item[] = NAV_PAGES.filter((p) => match(p.label)).map((p) => ({ group: 'Pages', ...p }))

    return q ? [...svc, ...actions, ...pages] : [...actions, ...pages]
  }, [query, services])

  function select(item: Item | undefined) {
    if (!item) return
    onClose()
    navigate(item.to)
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(i + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      select(items[active])
    }
  }

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [active])

  let lastGroup = ''

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 p-4 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={onKeyDown}
        className="mt-20 flex w-full max-w-lg animate-fade-in flex-col border-2 border-paper-line bg-paper-raised text-ink"
      >
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
          }}
          placeholder="Search services, pages, actions…"
          className="border-b-2 border-paper-line-soft bg-transparent px-4 py-3 font-body text-sm text-ink placeholder:text-ink-faint focus:outline-none"
        />
        {items.length === 0 ? (
          <p className="px-4 py-6 text-center font-body text-xs font-semibold uppercase tracking-wide text-ink-faint">
            No matches
          </p>
        ) : (
          <ul ref={listRef} className="max-h-80 overflow-y-auto py-1">
            {items.map((item, i) => {
              const header = item.group !== lastGroup ? item.group : null
              lastGroup = item.group
              return (
                <li key={`${item.group}:${item.to}:${item.label}`}>
                  {header && (
                    <p className="px-4 pb-1 pt-3 font-body text-[10px] font-bold uppercase tracking-[0.15em] text-ink-faint">
                      {header}
                    </p>
                  )}
                  <button
                    type="button"
                    data-active={i === active}
                    onMouseEnter={() => setActive(i)}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      select(item)
                    }}
                    className={`flex w-full items-baseline justify-between gap-3 px-4 py-2 text-left transition-colors ${
                      i === active ? 'bg-accent text-background' : 'hover:bg-paper'
                    }`}
                  >
                    <span className="truncate font-body text-sm font-bold">{item.label}</span>
                    {item.sub && (
                      <span
                        className={`shrink-0 font-body text-[11px] font-semibold uppercase tracking-wide ${
                          i === active ? 'text-background/80' : 'text-ink-faint'
                        }`}
                      >
                        {item.sub}
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

export function HeaderSearch() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Search the app"
        className="hidden w-full max-w-xl items-center gap-2 border-2 border-background/15 bg-background/5 py-1.5 pl-2.5 pr-2 text-background/50 transition-colors hover:border-background/30 sm:flex"
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-4 w-4 shrink-0">
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
          <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span className="flex-1 text-left font-body text-sm">Search…</span>
        <kbd className="shrink-0 border border-background/20 px-1 font-mono text-[10px] font-bold text-background/50">
          ⌘K
        </kbd>
      </button>
      {open && <CommandPalette onClose={() => setOpen(false)} />}
    </>
  )
}
