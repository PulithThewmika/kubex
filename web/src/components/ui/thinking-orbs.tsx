// Thinking Orbs — an animated thinking/agent orb.
// Source & playground: https://orbs.jakubantalik.com
//
// Vendored wrapper: the published <ThinkingOrb> freezes to a single static
// frame whenever `prefers-reduced-motion: reduce` is set. We drive the same
// engine (MODE_DRAWS + resolvePreset) ourselves so the orb always animates,
// keeping only the hidden-tab pause. Types come straight from the package.
import { useEffect, useRef } from 'react'
import type { CanvasHTMLAttributes, CSSProperties } from 'react'
import { MODE_DRAWS, resolvePreset } from 'thinking-orbs'

export type { OrbState, OrbSize, OrbTheme, ThinkingOrbProps } from 'thinking-orbs'
import type { OrbState, OrbSize, OrbTheme } from 'thinking-orbs'

type Props = Omit<CanvasHTMLAttributes<HTMLCanvasElement>, 'style'> & {
  state?: OrbState
  size?: OrbSize
  theme?: OrbTheme
  /** Multiplier on the preset's baked speed. @default 1 */
  speed?: number
  style?: CSSProperties
}

function resolveDark(theme: OrbTheme): boolean {
  if (theme === 'dark') return true
  if (theme === 'light') return false
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches
}

export function ThinkingOrb({ state = 'working', size = 64, theme = 'auto', speed = 1, style, ...rest }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(2, (typeof devicePixelRatio !== 'undefined' && devicePixelRatio) || 1)
    canvas.width = Math.round(size * dpr)
    canvas.height = Math.round(size * dpr)

    const { mode, speed: presetSpeed, opts } = resolvePreset(state, size)
    const draw = MODE_DRAWS[mode]
    const rate = presetSpeed * speed
    const dark = resolveDark(theme)

    const paint = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, size, size)
      draw(ctx, size, t, dark, opts)
    }

    let raf = 0
    let running = false
    const loop = () => {
      paint((performance.now() / 1000) * rate)
      if (running) raf = requestAnimationFrame(loop)
    }
    const start = () => {
      if (running) return
      running = true
      raf = requestAnimationFrame(loop)
    }
    const stop = () => {
      running = false
      cancelAnimationFrame(raf)
    }
    const onVisibility = () => (document.visibilityState === 'hidden' ? stop() : start())

    paint(0)
    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [state, size, theme, speed])

  return <canvas ref={ref} style={{ width: size, height: size, ...style }} {...rest} />
}

export default ThinkingOrb
