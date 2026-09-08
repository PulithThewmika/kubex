import { useAuth } from '../../contexts/AuthContext'

function Field({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="font-body text-xs font-bold uppercase tracking-wide text-ink">{label}</dt>
      <dd className="mt-1 text-sm text-ink-muted">{value}</dd>
      {hint && (
        <p className="mt-1.5 font-body text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{hint}</p>
      )}
    </div>
  )
}

export function GeneralTab() {
  const { user } = useAuth()

  return (
    <section>
      <h2 className="font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-muted">Organization</h2>
      <dl className="mt-4 flex flex-col gap-5">
        <Field label="Name" value={user?.org_name ?? '—'} />
        <Field
          label="Slug"
          value={user?.org_slug ?? '—'}
          hint="Taken from your GitHub organization. Managed on GitHub, not here."
        />
      </dl>
    </section>
  )
}
