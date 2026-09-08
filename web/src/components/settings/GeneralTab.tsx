import { useAuth } from '../../contexts/AuthContext'

function Field({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-sm font-medium text-text">{label}</dt>
      <dd className="mt-1 text-sm text-text-muted">{value}</dd>
      {hint && <p className="mt-1.5 text-xs text-text-muted">{hint}</p>}
    </div>
  )
}

export function GeneralTab() {
  const { user } = useAuth()

  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Organization</h2>
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
