import {
  Workflow,
  GitBranch,
  Hexagon,
  Flame,
  BarChart3,
  Hash,
  ScrollText,
  BellRing,
  type LucideIcon,
} from 'lucide-react'

// KubeX at the hub, every signal source wired to it with an elbow connector
// and a glowing comet running node → hub. Pure SVG + CSS — the animations
// (.graph-flow, .graph-float in index.css) need no motion library and freeze
// cleanly under prefers-reduced-motion. viewBox is 564 × 440, hub at 282,220.
type Node = {
  id: string
  label: string
  Icon: LucideIcon
  x: number
  y: number
  d: string
}

const NODES: Node[] = [
  { id: 'github', label: 'GitHub Actions', Icon: Workflow, x: 96, y: 70, d: 'M 96 70 H 214 Q 234 70 234 90 V 220' },
  { id: 'argocd', label: 'ArgoCD', Icon: GitBranch, x: 282, y: 54, d: 'M 282 54 V 220' },
  { id: 'prometheus', label: 'Prometheus', Icon: Flame, x: 468, y: 72, d: 'M 468 72 H 350 Q 330 72 330 92 V 220' },
  { id: 'loki', label: 'Loki', Icon: ScrollText, x: 66, y: 220, d: 'M 66 220 H 234' },
  { id: 'grafana', label: 'Grafana', Icon: BarChart3, x: 498, y: 220, d: 'M 498 220 H 330' },
  { id: 'slack', label: 'Slack', Icon: Hash, x: 150, y: 378, d: 'M 150 378 H 226 Q 246 378 246 358 V 220' },
  { id: 'kubernetes', label: 'Kubernetes', Icon: Hexagon, x: 282, y: 392, d: 'M 282 392 V 220' },
  { id: 'alertmanager', label: 'Alertmanager', Icon: BellRing, x: 474, y: 368, d: 'M 474 368 H 350 Q 330 368 330 348 V 220' },
]

export function IntegrationGraph({ className = '' }: { className?: string }) {
  return (
    <div
      role="img"
      aria-label={`KubeX correlates ${NODES.map((n) => n.label).join(', ')} into one deployment record`}
      className={`relative mx-auto aspect-[564/440] w-full max-w-md overflow-hidden ${className}`}
    >
      {/* Dot grid + vignette */}
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage: 'radial-gradient(circle, #6B717C 1px, transparent 1px)',
          backgroundSize: '26px 26px',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/50 via-transparent to-background/50"
      />

      {/* Connectors */}
      <svg viewBox="0 0 564 440" fill="none" className="absolute inset-0 h-full w-full">
        {NODES.map((n, i) => (
          <g key={n.id}>
            <path d={n.d} className="stroke-border-strong" strokeWidth={1.5} />
            <path
              d={n.d}
              pathLength={1}
              strokeLinecap="round"
              className="graph-flow graph-glow stroke-accent"
              strokeWidth={2}
              style={{ strokeDasharray: '0.16 1', animationDelay: `${i * 0.34}s` }}
            />
          </g>
        ))}
      </svg>

      {/* Hub — the KubeX mark */}
      <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
        <div className="graph-float" style={{ animationDuration: '6s' }}>
          <span
            aria-hidden="true"
            className="absolute -inset-2 rounded-2xl border border-accent/40 motion-safe:animate-pulse"
          />
          <div className="relative rounded-xl border-2 border-border-strong bg-background p-2.5 shadow-raised sm:rounded-2xl sm:p-3.5">
            <img
              src="/kubex-logo.png"
              alt=""
              aria-hidden="true"
              className="h-8 w-8 object-contain sm:h-11 sm:w-11"
            />
          </div>
        </div>
      </div>

      {/* Signal sources */}
      {NODES.map((n, i) => (
        <div
          key={n.id}
          style={{ left: `${(n.x / 564) * 100}%`, top: `${(n.y / 440) * 100}%` }}
          className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
        >
          <div
            title={n.label}
            className="graph-float flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-text shadow-card transition-colors hover:border-accent hover:text-accent sm:h-12 sm:w-12 sm:rounded-xl"
            style={{ animationDuration: `${4.2 + i * 0.5}s`, animationDelay: `${i * 0.3}s` }}
          >
            <n.Icon className="h-4 w-4 sm:h-5 sm:w-5" strokeWidth={1.75} aria-hidden="true" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default IntegrationGraph
