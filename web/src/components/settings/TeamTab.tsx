import { useMembers, type Member } from '../../hooks/useMembers'

function RoleBadge({ role }: { role: string }) {
  const isOwner = role === 'owner'
  return (
    <span
      className={`w-fit rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        isOwner ? 'bg-accent/10 text-accent' : 'bg-border text-text-muted'
      }`}
    >
      {role}
    </span>
  )
}

function MemberRow({ member }: { member: Member }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        {member.avatar_url ? (
          <img src={member.avatar_url} alt="" className="h-8 w-8 rounded-full" />
        ) : (
          <span
            aria-hidden="true"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-border text-xs font-medium uppercase text-text-muted"
          >
            {member.login.slice(0, 2)}
          </span>
        )}
        <span className="text-sm font-medium text-text">{member.login}</span>
      </div>
      <RoleBadge role={member.role} />
    </li>
  )
}

export function TeamTab() {
  const { data: members, isLoading, isError } = useMembers()

  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Team</h2>
      <p className="mt-1 text-sm text-text-muted">People with access to this organization.</p>

      <div className="mt-4">
        {isLoading && <p className="text-sm text-text-muted">Loading members…</p>}
        {isError && <p className="text-sm text-failed">Failed to load members.</p>}
        {members && members.length > 0 && (
          <ul className="flex flex-col gap-3">
            {members.map((member) => (
              <MemberRow key={member.user_id} member={member} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
