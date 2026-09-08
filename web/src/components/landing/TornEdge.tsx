// A ripped-paper divider. Drop it at the very top of a section with a
// negative top margin so the section's colour tears up into whatever sits
// above it. `tone` is the section's own background colour.
type Tone = 'background' | 'accent' | 'text'

const FILL: Record<Tone, string> = {
  background: '#0A0B0D',
  accent: '#FF5722',
  text: '#E6E8EB',
}

// One hand-irregular jagged line across a 1200-wide viewBox.
const JAG =
  'M0,40 L0,17 L38,23 L84,7 L132,19 L184,11 L242,25 L300,9 L360,21 L424,5 ' +
  'L494,19 L556,13 L618,27 L688,11 L748,23 L812,7 L882,21 L942,13 L1012,26 ' +
  'L1072,9 L1132,21 L1200,13 L1200,40 Z'

export function TornEdge({
  tone,
  flip = false,
  className = '',
}: {
  tone: Tone
  flip?: boolean
  className?: string
}) {
  return (
    <svg
      viewBox="0 0 1200 40"
      preserveAspectRatio="none"
      aria-hidden="true"
      className={`pointer-events-none block h-6 w-full sm:h-10 ${flip ? 'rotate-180' : ''} ${className}`}
    >
      <path d={JAG} fill={FILL[tone]} />
    </svg>
  )
}
