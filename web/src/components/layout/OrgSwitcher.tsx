import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useMemberships } from '../../hooks/useMemberships'
import { apiFetch } from '../../lib/apiFetch'

export function OrgSwitcher({ onSwitched }: { onSwitched: () => void }) {
  const { user } = useAuth()
  const { data: memberships } = useMemberships(!!user)
  const [switching, setSwitching] = useState(false)

  if (!memberships || memberships.length <= 1) return null

  async function handleSwitch(orgId: string) {
    if (orgId === user?.org_id || switching) return
    setSwitching(true)
    try {
      const res = await apiFetch('/auth/switch-org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_id: orgId }),
      })
      if (res.ok) {
        onSwitched()
        // ponytail: full reload rather than selectively invalidating every
        // org-scoped query cache entry — correct and simple; revisit if
        // reload latency becomes a real complaint.
        window.location.reload()
      }
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="border-b-2 border-text py-1">
      <p className="px-3 pb-1 pt-1.5 font-body text-[11px] font-bold uppercase tracking-wide text-text-faint">
        Switch organization
      </p>
      {memberships.map((m) => {
        const active = m.org_id === user?.org_id
        return (
          <button
            key={m.org_id}
            type="button"
            role="menuitem"
            disabled={switching}
            onClick={() => handleSwitch(m.org_id)}
            className={`flex w-full items-center justify-between px-3 py-2 text-left font-body text-xs font-bold uppercase tracking-wide transition-colors hover:bg-surface disabled:opacity-50 ${
              active ? 'text-accent' : 'text-text-muted hover:text-text'
            }`}
          >
            <span className="truncate">{m.org_name}</span>
            {active && (
              <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4 shrink-0" aria-hidden="true">
                <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        )
      })}
    </div>
  )
}
