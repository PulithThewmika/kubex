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

// KubeX at the hub, every signal source wired to it. Pure SVG + CSS — the
// travelling pulse is a dash animation (see .graph-flow in index.css), so it
// needs no motion library and freezes cleanly under prefers-reduced-motion.
type Node = { id: string; label: string; Icon: LucideIcon }

const NODES: Node[] = [
  { id: 'github', label: 'GitHub Actions', Icon: Workflow },
  { id: 'argocd', label: 'ArgoCD', Icon: GitBranch },
  { id: 'prometheus', label: 'Prometheus', Icon: Flame },
  { id: 'grafana', label: 'Grafana', Icon: BarChart3 },
  { id: 'slack', label: 'Slack', Icon: Hash },
  { id: 'alertmanager', label: 'Alertmanager', Icon: BellRing },
  { id: 'loki', label: 'Loki', Icon: ScrollText },
  { id: 'kubernetes', label: 'Kubernetes', Icon: Hexagon },
]

const C = 200 // viewBox centre
const R = 132 // hub → node radius
const PATH_LEN = R

export function IntegrationGraph({ className = '' }: { className?: string }) {
  const nodes = NODES.map((n, i) => {
    const a = ((-90 + i * (360 / NODES.length)) * Math.PI) / 180
    return { ...n, x: C + R * Math.cos(a), y: C + R * Math.sin(a) }
  })

  return (
    <div
      role="img"
      aria-label={`KubeX correlates ${NODES.map((n) => n.label).join(', ')} into one deployment record`}
      className={`relative mx-auto aspect-square w-full max-w-xs sm:max-w-md ${className}`}
    >
      <svg viewBox="0 0 400 400" fill="none" className="absolute inset-0 h-full w-full">
        {nodes.map((n, i) => {
          const d = `M ${n.x.toFixed(1)} ${n.y.toFixed(1)} L ${C} ${C}`
          return (
            <g key={n.id}>
              <path d={d} strokeWidth={1.5} className="stroke-border-strong" />
              <path
                d={d}
                strokeWidth={2.5}
                strokeLinecap="round"
                className="graph-flow stroke-accent"
                style={{
                  strokeDasharray: `14 ${PATH_LEN * 3}`,
                  animationDelay: `${i * 0.28}s`,
                }}
              />
            </g>
          )
        })}
      </svg>

      {/* Hub — the KubeX mark */}
      <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
        <span
          aria-hidden="true"
          className="absolute -inset-2 rounded-2xl border-2 border-accent/30 motion-safe:animate-pulse"
        />
        <div className="relative border-2 border-text bg-background p-2 shadow-raised sm:p-3">
          <img
            src="/kubex-logo.png"
            alt=""
            aria-hidden="true"
            className="h-9 w-9 object-contain sm:h-12 sm:w-12"
          />
        </div>
      </div>

      {/* Signal sources */}
      {nodes.map((n) => (
        <div
          key={n.id}
          title={n.label}
          style={{ left: `${(n.x / 400) * 100}%`, top: `${(n.y / 400) * 100}%` }}
          className="absolute z-10 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center border-2 border-border-strong bg-surface text-accent transition-colors hover:border-accent sm:h-12 sm:w-12"
        >
          <n.Icon className="h-4 w-4 sm:h-5 sm:w-5" strokeWidth={1.75} aria-hidden="true" />
        </div>
      ))}
    </div>
  )
}

export default IntegrationGraph
