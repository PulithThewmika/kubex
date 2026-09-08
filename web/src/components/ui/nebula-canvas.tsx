import { useEffect, useRef } from 'react'

/**
 * Themed reimplementation of the 21st.dev "Neon Nebula" ASCII effect for one
 * fixed preset:
 *   renderMode "stars" · bgMode solid · cellSize 16 · coverage 100
 *   an animated RADIAL gradient (Mauve→Violet→Midnight→Ink, here remapped to
 *   KubeX ember-orange → ink) with wave + distortion + slow centre drift
 *   brightness +12, contrast 115
 *   animStyle "wave", full speed, 60% intensity
 *   post-fx the preset enables: vignette 38 · scanLines 40 · bloom 25 ·
 *   filmGrain 30 · halftone 20  (pixelate is redundant against 16px cells)
 *
 * Everything is Canvas2D. Honours prefers-reduced-motion by painting a single
 * frame and stopping.
 */

const CELL = 16
const FPS = 30

// Mauve / Violet / Midnight / Ink → ember / accent / burnt / background.
const STOPS: { pos: number; rgb: [number, number, number] }[] = [
  { pos: 0.0, rgb: [255, 178, 128] },
  { pos: 0.33, rgb: [255, 87, 34] },
  { pos: 0.67, rgb: [74, 20, 8] },
  { pos: 1.0, rgb: [10, 11, 13] },
]

// Cheap per-cell hash → 0..1, so the star field twinkles instead of reading
// as a regular halftone grid.
const hash = (x: number, y: number) => {
  const n = Math.sin(x * 127.1 + y * 311.7) * 43758.5453
  return n - Math.floor(n)
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const clamp8 = (n: number) => (n < 0 ? 0 : n > 255 ? 255 : n)

function samplePalette(t: number): [number, number, number] {
  t = t < 0 ? 0 : t > 1 ? 1 : t
  for (let i = 1; i < STOPS.length; i++) {
    const a = STOPS[i - 1]
    const b = STOPS[i]
    if (t <= b.pos) {
      const k = (t - a.pos) / (b.pos - a.pos || 1)
      return [lerp(a.rgb[0], b.rgb[0], k), lerp(a.rgb[1], b.rgb[1], k), lerp(a.rgb[2], b.rgb[2], k)]
    }
  }
  return STOPS[STOPS.length - 1].rgb
}

// brightness +12, contrast 115 — applied to the sampled colour.
function adjust(c: [number, number, number]): [number, number, number] {
  const bri = (12 / 100) * 128
  const ct = 1.15
  return [
    clamp8((c[0] + bri - 128) * ct + 128),
    clamp8((c[1] + bri - 128) * ct + 128),
    clamp8((c[2] + bri - 128) * ct + 128),
  ]
}

// Radial gradient field: 0 at the (drifting) centre → 1 at the edge, warped by
// a travelling wave (gradientSource.wave 12 / distortion 28 / motion 86).
function field(u: number, v: number, time: number): number {
  const cx = 0.62 + Math.sin(time * 0.18) * 0.05
  const cy = 0.42 + Math.cos(time * 0.13) * 0.04
  const dx = u - cx
  const dy = v - cy
  const dist = Math.hypot(dx, dy)
  const wave = Math.sin(dist * 9 - time * 1.4) * 0.07
  const swirl = Math.sin(Math.atan2(dy, dx) * 3 + time * 0.6) * 0.035
  let r = dist / 0.95 + wave + swirl
  r = Math.pow(r < 0 ? 0 : r, 0.82) // softness 26
  return r
}

function makeNoise(size: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = c.height = size
  const cx = c.getContext('2d')!
  const img = cx.createImageData(size, size)
  for (let i = 0; i < img.data.length; i += 4) {
    const n = (Math.random() * 255) | 0
    img.data[i] = img.data[i + 1] = img.data[i + 2] = n
    img.data[i + 3] = 255
  }
  cx.putImageData(img, 0, 0)
  return c
}

function star(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  const i = s * 0.34
  ctx.beginPath()
  ctx.moveTo(x, y - s)
  ctx.quadraticCurveTo(x + i * 0.4, y - i * 0.4, x + s, y)
  ctx.quadraticCurveTo(x + i * 0.4, y + i * 0.4, x, y + s)
  ctx.quadraticCurveTo(x - i * 0.4, y + i * 0.4, x - s, y)
  ctx.quadraticCurveTo(x - i * 0.4, y - i * 0.4, x, y - s)
  ctx.closePath()
  ctx.fill()
}

export function NebulaCanvas({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const noise = makeNoise(140)
    let raf = 0
    let last = 0
    let w = 0
    let h = 0
    let dpr = 1

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = Math.max(1, Math.round(rect.width))
      h = Math.max(1, Math.round(rect.height))
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = (time: number) => {
      const cols = Math.ceil(w / CELL)
      const rows = Math.ceil(h / CELL)

      // 1–3. gradient field → per-cell star, sized/coloured by luminance,
      // nudged by the wave animation (animIntensity 60).
      ctx.fillStyle = '#0A0B0D'
      ctx.fillRect(0, 0, w, h)

      for (let gy = 0; gy < rows; gy++) {
        for (let gx = 0; gx < cols; gx++) {
          const rnd = hash(gx, gy)
          if (rnd < 0.16) continue // sparser than a full grid — reads as stars
          const u = (gx + 0.5) / cols
          const v = (gy + 0.5) / rows
          const wobble = Math.sin(gx * 0.55 + gy * 0.32 - time * 2.1) * 0.36
          const twinkle = 0.55 + 0.45 * Math.sin(time * 3 + rnd * 12)
          const t = field(u, v, time) - wobble * 0.05
          const [r, g, b] = adjust(samplePalette(t))
          const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
          if (lum < 0.045) continue
          const s = lum * CELL * (0.5 + 0.9 * rnd) * (0.7 + 0.5 * (1 + wobble)) * twinkle
          ctx.globalAlpha = Math.min(1, lum * 1.3 * twinkle)
          ctx.fillStyle = `rgb(${r | 0},${g | 0},${b | 0})`
          star(ctx, gx * CELL + CELL / 2, gy * CELL + CELL / 2, Math.max(0.5, s * 0.6))
        }
      }
      ctx.globalAlpha = 1

      // 5. bloom 25 — additive blurred copy of the bright pixels.
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      ctx.globalAlpha = 0.32
      ctx.filter = 'blur(8px)'
      ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, w, h)
      ctx.restore()

      // 5. halftone 20 — soft dot screen.
      ctx.save()
      ctx.globalCompositeOperation = 'multiply'
      ctx.globalAlpha = 0.12
      ctx.fillStyle = '#000'
      for (let y = 0; y < h; y += 9) {
        for (let x = (y % 18 === 0 ? 0 : 4.5); x < w; x += 9) {
          ctx.beginPath()
          ctx.arc(x, y, 1, 0, Math.PI * 2)
          ctx.fill()
        }
      }
      ctx.restore()

      // 5. scan lines 40.
      ctx.save()
      ctx.globalAlpha = 0.16
      ctx.fillStyle = '#000'
      for (let y = 0; y < h; y += 3) ctx.fillRect(0, y, w, 1)
      ctx.restore()

      // 5. film grain 30 — noise tile at a random offset each frame.
      ctx.save()
      ctx.globalCompositeOperation = 'overlay'
      ctx.globalAlpha = 0.09
      const ox = -((Math.random() * 140) | 0)
      const oy = -((Math.random() * 140) | 0)
      for (let y = oy; y < h; y += 140) for (let x = ox; x < w; x += 140) ctx.drawImage(noise, x, y)
      ctx.restore()

      // 5. vignette 38.
      const vg = ctx.createRadialGradient(w * 0.5, h * 0.5, Math.min(w, h) * 0.2, w * 0.5, h * 0.5, Math.max(w, h) * 0.72)
      vg.addColorStop(0, 'rgba(0,0,0,0)')
      vg.addColorStop(1, 'rgba(0,0,0,0.62)')
      ctx.fillStyle = vg
      ctx.fillRect(0, 0, w, h)
    }

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      if (now - last < 1000 / FPS) return
      last = now
      draw(now / 1000)
    }

    resize()
    if (reduce) {
      draw(0)
    } else {
      raf = requestAnimationFrame(loop)
    }
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={ref} aria-hidden="true" className={className} />
}

export default NebulaCanvas
