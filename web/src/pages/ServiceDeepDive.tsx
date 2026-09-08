import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { DeployDiffTable } from '../components/DeployDiffTable'
import { GrafanaPanel } from '../components/GrafanaPanel'
import { PipelineTimeline } from '../components/PipelineTimeline'
import { useCompare } from '../hooks/useCompare'
import { useDeployments } from '../hooks/useDeployments'
import { useDORA } from '../hooks/useDORA'
import { useServices } from '../hooks/useServices'
import { formatDuration } from '../lib/timeline'
import type { Deployment } from '../types/deployment'
import type { DORAMetrics } from '../types/dora'

export function ServiceDeepDive() {
  const { name = '' } = useParams<{ name: string }>()
  const { data: deployments, isLoading: deploymentsLoading, isError: deploymentsError } = useDeployments(name)
  const { data: dora } = useDORA(name)
  const { data: services } = useServices()
  const service = services?.find((s) => s.name === name)

  return (
    <div className="flex flex-col gap-6 p-6">
      <ServiceHeader
        name={name}
        status={service?.latest_deploy?.status ?? null}
        environment={service?.namespace ?? null}
        dora={dora}
      />
      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-xs font-bold uppercase tracking-[0.15em] text-text-muted">
          Pipeline timeline
        </h2>
        {deploymentsError ? (
          <div className="border-2 border-failed bg-failed/5 p-4 font-body text-xs font-bold uppercase tracking-wide text-failed">
            Failed to load deployments. Retrying automatically.
          </div>
        ) : !deploymentsLoading && deployments?.length === 0 ? (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            No deployments yet for this service.
          </p>
        ) : deploymentsLoading ? (
          <div className="h-40 animate-pulse border-2 border-border-strong bg-surface" />
        ) : (
          <PipelineTimeline deployments={deployments ?? []} />
        )}
      </section>
      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-xs font-bold uppercase tracking-[0.15em] text-text-muted">Metrics</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <GrafanaPanel uid="deploy-timeline" panelId={1} service={name} title="Error Rate" />
          <GrafanaPanel uid="deploy-timeline" panelId={2} service={name} title="p99 Latency" />
        </div>
      </section>
      {deployments && deployments.length > 0 && <CompareSection deployments={deployments} />}
    </div>
  )
}

type CompareSectionProps = {
  deployments: Deployment[]
}

function CompareSection({ deployments }: CompareSectionProps) {
  const [active, setActive] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const { data: compareResult, isLoading: compareLoading, isError: compareError } = useCompare(
    selected[0] ?? null,
    selected[1] ?? null,
  )

  function toggle(id: number) {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((s) => s !== id)
      if (prev.length >= 2) return prev
      return [...prev, id]
    })
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xs font-bold uppercase tracking-[0.15em] text-text-muted">Compare</h2>
        <button
          type="button"
          onClick={() => {
            setActive((a) => !a)
            setSelected([])
          }}
          className="border-2 border-text-muted px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-text-muted transition-colors hover:border-accent hover:text-accent"
        >
          {active ? 'Cancel' : 'Compare deployments'}
        </button>
      </div>
      {active && (
        <div className="flex flex-col gap-2">
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            Select two deployments to compare ({selected.length}/2).
          </p>
          {deployments.map((d) => {
            const shortSha = d.commit_sha ? d.commit_sha.slice(0, 7) : d.status
            const checked = selected.includes(d.id)
            const disabled = !checked && selected.length >= 2
            return (
              <label
                key={d.id}
                className={`flex items-center gap-2 border-2 bg-surface px-3 py-2 font-body text-sm transition-colors ${
                  checked ? 'border-accent' : 'border-border-strong'
                } ${disabled ? 'opacity-50' : 'hover:border-text'}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => toggle(d.id)}
                  className="accent-accent"
                />
                <span className="font-mono text-text">{shortSha}</span>
                <span className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {d.author ?? 'unknown'}
                </span>
              </label>
            )
          })}
          {selected.length === 2 && (
            <>
              {compareError && (
                <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
                  Failed to load comparison.
                </p>
              )}
              {compareLoading && <div className="h-32 animate-pulse border-2 border-border-strong bg-surface" />}
              {compareResult && <DeployDiffTable metrics={compareResult.metrics} />}
            </>
          )}
        </div>
      )}
    </section>
  )
}

type ServiceHeaderProps = {
  name: string
  status: string | null
  environment: string | null
  dora: DORAMetrics | undefined
}

function ServiceHeader({ name, status, environment, dora }: ServiceHeaderProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 border-b-2 border-text pb-5">
        <h1 className="font-heading text-2xl font-bold uppercase tracking-tight text-text sm:text-3xl">{name}</h1>
        {status && (
          <span className="border-2 border-border-strong bg-surface px-2 py-0.5 font-body text-xs font-bold uppercase tracking-wide text-text-muted">
            {status}
          </span>
        )}
        {environment && (
          <span className="border border-border-strong bg-background px-1.5 py-0.5 font-mono text-[11px] text-text-muted">
            {environment}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <DoraStat label="Deploy frequency" value={formatFrequency(dora?.deploy_frequency_per_day)} />
        <DoraStat label="Lead time" value={formatSeconds(dora?.lead_time_avg_s)} />
        <DoraStat label="Change failure rate" value={formatPercent(dora?.change_failure_rate)} />
        <DoraStat label="MTTR" value={formatSeconds(dora?.mttr_s)} />
      </div>
    </div>
  )
}

function DoraStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-2 border-border-strong bg-surface p-3">
      <div className="font-body text-[11px] font-bold uppercase tracking-wide text-text-faint">{label}</div>
      <div className="mt-0.5 font-heading text-xl font-bold tabular-nums text-text">{value}</div>
    </div>
  )
}

function formatFrequency(perDay: number | null | undefined): string {
  if (perDay === null || perDay === undefined) return '—'
  return `${perDay.toFixed(2)}/day`
}

function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  return formatDuration(seconds)
}

function formatPercent(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined) return '—'
  return `${(fraction * 100).toFixed(1)}%`
}
