const ITEMS = [
  'GitHub Actions',
  'ArgoCD',
  'Kubernetes',
  'Prometheus',
  'Grafana',
  'Slack',
  'Loki',
  'Alertmanager',
  'DORA metrics',
  'Health scoring',
  'Blast radius',
  'Safety scores',
]

// Scrolling strip of the surface KubeX reads. Bracket a section with a normal
// and a reversed one for the ripped-newsprint feel.
export function Ticker({
  reverse = false,
  tone = 'accent',
}: {
  reverse?: boolean
  tone?: 'accent' | 'text'
}) {
  const skin = tone === 'accent' ? 'bg-accent text-background' : 'bg-text text-background'
  return (
    <div className={`marquee border-y-2 border-text ${skin}`} aria-hidden="true">
      <div className={`marquee-track py-2 ${reverse ? 'marquee-track--rev' : ''}`}>
        {[...ITEMS, ...ITEMS].map((t, i) => (
          <span key={i} className="inline-flex items-center font-display text-lg uppercase tracking-wider sm:text-2xl">
            <span className="px-4">{t}</span>
            <span className="opacity-50">✦</span>
          </span>
        ))}
      </div>
    </div>
  )
}
