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
        className="flex h-8 w-8 items-center justify-center overflow-hidden border-2 border-text-muted bg-accent/10 font-body text-xs font-bold text-accent transition-colors hover:border-accent"
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
          className="absolute right-0 top-11 z-30 w-60 origin-top-right animate-fade-in overflow-hidden border-2 border-text bg-surface-raised py-1"
        >
          <div className="border-b-2 border-text px-3 py-2.5">
            <p className="truncate font-body text-sm font-bold text-text">{user.login}</p>
            {user.org_name && (
              <p className="truncate font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
                {user.org_name}
              </p>
            )}
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
              className="block w-full px-3 py-2 text-left font-body text-xs font-bold uppercase tracking-wide text-text-muted transition-colors hover:bg-surface hover:text-accent"
            >
              Settings
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="block w-full px-3 py-2 text-left font-body text-xs font-bold uppercase tracking-wide text-text-muted transition-colors hover:bg-surface hover:text-accent"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
