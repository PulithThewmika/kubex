import { HeaderAlertsBell } from './HeaderAlertsBell'
import { HeaderConnections } from './HeaderConnections'
import { HeaderQuickAdd } from './HeaderQuickAdd'
import { HeaderSearch } from './HeaderSearch'
import { UserMenu } from './UserMenu'

type TopBarProps = {
  sidebarHidden: boolean
  onToggleSidebar: () => void
}

export function TopBar({ sidebarHidden, onToggleSidebar }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b-2 border-background bg-text px-4 text-background sm:px-6">
      <button
        type="button"
        onClick={onToggleSidebar}
        aria-label={sidebarHidden ? 'Show sidebar' : 'Hide sidebar'}
        aria-pressed={sidebarHidden}
        className="flex h-8 w-8 shrink-0 items-center justify-center border-2 border-background/20 text-background/70 transition-colors hover:border-accent hover:text-accent"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
          <rect x="3" y="4" width="18" height="16" rx="1" stroke="currentColor" strokeWidth="2" />
          <path d="M9 4v16" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>
      <HeaderSearch />
      <div className="ml-auto flex items-center gap-2 sm:gap-3">
        <HeaderQuickAdd />
        <HeaderAlertsBell />
        <HeaderConnections />
        <span className="h-6 w-px bg-background/20" aria-hidden="true" />
        <UserMenu />
      </div>
    </header>
  )
}
