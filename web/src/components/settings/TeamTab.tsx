import { useMembers, type Member } from '../../hooks/useMembers'

function RoleBadge({ role }: { role: string }) {
  const isOwner = role === 'owner'
  return (
    <span
      className={`w-fit border px-2 py-0.5 font-body text-xs font-bold uppercase tracking-wide ${
        isOwner ? 'border-accent bg-accent/10 text-accent' : 'border-border-strong bg-border text-text-muted'
      }`}
    >
      {role}
    </span>
  )
}

function MemberRow({ member }: { member: Member }) {
  return (
    <li className="flex items-center justify-between gap-3 border-2 border-border-strong bg-surface p-4">
      <div className="flex items-center gap-3">
        {member.avatar_url ? (
          <img src={member.avatar_url} alt="" className="h-8 w-8 rounded-full" />
        ) : (
          <span
            aria-hidden="true"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-border font-body text-xs font-bold uppercase text-text-muted"
          >
            {member.login.slice(0, 2)}
          </span>
        )}
        <span className="font-body text-sm font-bold text-text">{member.login}</span>
      </div>
      <RoleBadge role={member.role} />
    </li>
  )
}

export function TeamTab() {
  const { data: members, isLoading, isError } = useMembers()

  return (
    <section>
      <h2 className="font-body text-xs font-bold uppercase tracking-[0.15em] text-text-muted">Team</h2>
      <p className="mt-1 font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
        People with access to this organization.
      </p>

      <div className="mt-4">
        {isLoading && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            Loading members…
          </p>
        )}
        {isError && (
          <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
            Failed to load members.
          </p>
        )}
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
