import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { OrgSwitcher } from './OrgSwitcher'
import { useOnClickOutside } from '../../hooks/useOnClickOutside'

function initials(login: string): string {
  return login.slice(0, 2).toUpperCase()
}

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useOnClickOutside(ref, () => setOpen(false))

  if (!user) return null

  async function handleSignOut() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="User menu"
        className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-accent/10 text-xs font-medium text-accent ring-1 ring-border transition-colors hover:ring-border-strong"
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
        ) : (
          initials(user.login)
        )}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-11 z-30 w-60 origin-top-right animate-fade-in overflow-hidden rounded-lg border border-border bg-surface-raised py-1 shadow-raised"
        >
          <div className="border-b border-border px-3 py-2.5">
            <p className="truncate text-sm font-medium text-text">{user.login}</p>
            {user.org_name && <p className="truncate text-xs text-text-muted">{user.org_name}</p>}
          </div>
          <OrgSwitcher onSwitched={() => setOpen(false)} />
          <div className="py-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                navigate('/app/settings')
              }}
              className="block w-full px-3 py-2 text-left text-sm text-text-muted transition-colors hover:bg-surface hover:text-text"
            >
              Settings
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="block w-full px-3 py-2 text-left text-sm text-text-muted transition-colors hover:bg-surface hover:text-text"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
