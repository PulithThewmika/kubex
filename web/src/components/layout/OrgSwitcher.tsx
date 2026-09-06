import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useMemberships } from '../../hooks/useMemberships'

export function OrgSwitcher({ onSwitched }: { onSwitched: () => void }) {
  const { user } = useAuth()
  const { data: memberships } = useMemberships(!!user)
  const [switching, setSwitching] = useState(false)

  if (!memberships || memberships.length <= 1) return null

  async function handleSwitch(orgId: string) {
    if (orgId === user?.org_id || switching) return
    setSwitching(true)
    try {
      const res = await fetch('/auth/switch-org', {
        method: 'POST',
        credentials: 'include',
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
    <div className="border-b border-border py-1">
      <p className="px-3 pb-1 pt-1 text-xs font-medium uppercase text-text-muted">Switch organization</p>
      {memberships.map((m) => (
        <button
          key={m.org_id}
          type="button"
          role="menuitem"
          disabled={switching}
          onClick={() => handleSwitch(m.org_id)}
          className={`block w-full px-3 py-2 text-left text-sm hover:bg-background disabled:opacity-50 ${
            m.org_id === user?.org_id ? 'font-medium text-accent' : 'text-text'
          }`}
        >
          {m.org_name}
        </button>
      ))}
    </div>
  )
}
