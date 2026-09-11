import type { ReactNode } from 'react'
import {
  GitHubActionsLogo,
  ArgoLogo,
  KubernetesLogo,
  PrometheusLogo,
  GrafanaLogo,
  SlackLogo,
  LokiLogo,
  GeminiLogo,
} from '../icons/brand-logos'
import { Reveal } from './Reveal'
import { Ticker } from './Ticker'

type Integration = {
  name: string
  role: string
  tag: string
  Icon: (props: { className?: string; strokeWidth?: number; 'aria-hidden'?: boolean | 'true' | 'false' }) => ReactNode
}

const INTEGRATIONS: Integration[] = [
  { name: 'GitHub Actions', role: 'Every workflow run, ingested via the GitHub App — no secrets to copy.', tag: 'CI', Icon: GitHubActionsLogo },
  { name: 'ArgoCD', role: 'Sync and rollout events, correlated back to the commit that triggered them.', tag: 'CD', Icon: ArgoLogo },
  { name: 'Kubernetes', role: 'Pod health, restarts and readiness from a lightweight in-cluster agent.', tag: 'RUNTIME', Icon: KubernetesLogo },
  { name: 'Prometheus', role: 'Error rate and latency deltas — the raw signal behind every health score.', tag: 'METRICS', Icon: PrometheusLogo },
  { name: 'Grafana', role: 'Per-deployment panels and DORA dashboards, embedded straight into the shell.', tag: 'DASHBOARDS', Icon: GrafanaLogo },
  { name: 'Slack', role: 'Degraded and failed deploys page your team the moment scoring completes.', tag: 'ALERTS', Icon: SlackLogo },
  { name: 'Loki', role: 'Logs from the blast radius, time-boxed to the deployment window.', tag: 'LOGS', Icon: LokiLogo },
  { name: 'Gemini', role: 'Ask the in-app chat about any deployment — it reads your live data via MCP.', tag: 'AI', Icon: GeminiLogo },
]

export function MaxIntegrations() {
  return (
    <section id="integrations" className="relative overflow-hidden bg-background">
      <Ticker />
      <div
        aria-hidden="true"
        className="absolute inset-0 text-accent/[0.07] halftone-lg"
      />
      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6 sm:pb-28">
        <Reveal>
          <p className="font-body text-xs font-bold uppercase tracking-[0.3em] text-accent">Plug it in</p>
          <h2 className="mt-3 font-display text-6xl uppercase leading-[0.85] text-text sm:text-8xl lg:text-9xl">
            Our <span className="text-accent">integrations</span>
          </h2>
          <p className="mt-6 max-w-xl font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
            KubeX doesn't replace your stack — it reads it. Connect the tools you
            already run and every signal lands in one deployment record.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-px overflow-hidden border-2 border-text bg-text sm:grid-cols-2 lg:grid-cols-4">
          {INTEGRATIONS.map((it, i) => (
            <Reveal key={it.name} delayMs={(i % 4) * 80}>
              <article className="group flex h-full flex-col justify-between gap-8 bg-background p-6 transition-colors hover:bg-accent">
                <div className="flex items-start justify-between">
                  <it.Icon
                    className="h-10 w-10 text-accent transition-colors group-hover:text-background"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  <span className="border border-text-faint px-1.5 py-0.5 font-body text-[10px] font-bold uppercase tracking-widest text-text-faint transition-colors group-hover:border-background group-hover:text-background">
                    {it.tag}
                  </span>
                </div>
                <div>
                  <h3 className="font-display text-2xl uppercase leading-none text-text transition-colors group-hover:text-background">
                    {it.name}
                  </h3>
                  <p className="mt-2 font-body text-xs leading-relaxed text-text-muted transition-colors group-hover:text-background/80">
                    {it.role}
                  </p>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
      {/* z-20 so the next section's torn edge (negative top margin) tears in
          behind the bar, not over it. */}
      <div className="relative z-20">
        <Ticker reverse />
      </div>
    </section>
  )
}
