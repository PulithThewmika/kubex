import { useEffect, useState } from 'react'
import tailwindConfig from '../../tailwind.config'

const VERDICT_COLORS: Record<string, string> = {
  healthy: '#3FB950',
  degraded: '#D29922',
  failed: '#F85149',
}

const TRACK_COLOR = tailwindConfig.theme.extend.colors['paper-line-soft']

type HealthRingProps = {
  score: number | null
  verdict: string | null
  size?: number
}

export function HealthRing({ score, verdict, size = 56 }: HealthRingProps) {
  const strokeWidth = Math.max(3, Math.round(size / 12))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const isUnknown = score === null
  const clampedScore = Math.min(100, Math.max(0, score ?? 0))
  const targetOffset = isUnknown ? 0 : circumference * (1 - clampedScore / 100)
  const color = isUnknown ? '#4B5563' : (verdict ? VERDICT_COLORS[verdict] : undefined) ?? TRACK_COLOR

  const [swept, setSwept] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setSwept(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <div
      role="img"
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      title={isUnknown ? 'Connect metrics to see a health score' : undefined}
      aria-label={
        isUnknown
          ? 'Health score unknown — connect metrics'
          : `Health score ${Math.round(clampedScore)}${verdict ? `, ${verdict}` : ''}`
      }
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={TRACK_COLOR}
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={swept ? targetOffset : circumference}
          style={{ transition: 'stroke-dashoffset 0.5s ease-out' }}
        />
      </svg>
      <span
        className={`absolute font-heading font-bold tabular-nums ${isUnknown ? 'text-ink-muted' : 'text-ink'}`}
        style={{ fontSize: size * 0.32 }}
      >
        {isUnknown ? '?' : Math.round(clampedScore)}
      </span>
    </div>
  )
}
