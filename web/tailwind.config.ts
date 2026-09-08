import type { Config } from 'tailwindcss'

// KubeX design system — dark-tech observability.
// Direction: a single cool-tinted near-black surface ladder (not pure black),
// a luminous green as the one accent, and a GitHub-Primer-adjacent status
// palette (green/amber/red/blue) that the SRE audience already reads fluently
// and that clears WCAG AA on the dark surfaces. Dark-only by design for the
// marketing/auth surface and the app shell's chrome (Sidebar/TopBar) — dark
// is the product's identity there, not a mode. The one deliberate exception
// is the app shell's *content* canvas (see the `paper`/`ink` ladder below),
// which runs the landing page's white-maximalist treatment instead.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surface ladder — each step ~one elevation up from the last.
        background: '#0A0B0D',
        surface: '#131519',
        'surface-raised': '#1B1E24',
        border: '#262A31',
        'border-strong': '#363B44',

        // The one accent — a warm poster orange (Material Deep Orange 500).
        // Warmer and easier on the eye than a neon green over long reading,
        // and it's the maximalist landing's single hot colour. Kept clear of
        // the muted `healthy` status green so it never reads as state.
        accent: '#FF5722',
        'accent-hover': '#FF7A50',

        // Text ladder.
        text: '#E6E8EB',
        'text-muted': '#9BA1AC',
        'text-faint': '#6B717C',

        // Status palette — reserved for state, never decorative. Ships with an
        // icon or label everywhere, never colour alone.
        healthy: '#3FB950',
        degraded: '#D29922',
        failed: '#F85149',
        info: '#58A6FF',

        // "Paper" ladder — the app shell's *content* canvas (everything
        // Sidebar/TopBar frame — Overview through Settings, including
        // /app/onboarding). Chrome (Sidebar, TopBar) stays on the dark
        // ladder above; only the scrollable content region switches to
        // this white maximalist canvas. Status colours above are reused
        // as-is on paper — each ships with an icon/label, never colour
        // alone, so the swap doesn't need paper-specific variants.
        paper: '#FAFAF7',
        'paper-raised': '#FFFFFF',
        'paper-line': '#16171A',
        'paper-line-soft': '#DCD8CE',
        ink: '#16171A',
        'ink-muted': '#57534A',
        'ink-faint': '#8C877A',
      },
      fontFamily: {
        // Maximalist poster display face for the marketing site — condensed,
        // heavy, all-caps. Never used inside the app shell.
        display: ['Anton', 'Impact', 'Haettenschweiler', 'system-ui', 'sans-serif'],
        heading: ['Mohave', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        // Tinted to the background hue, not pure black at low opacity.
        card: '0 1px 2px rgba(3, 4, 6, 0.4), 0 1px 3px rgba(3, 4, 6, 0.3)',
        raised: '0 12px 32px -8px rgba(3, 4, 6, 0.6), 0 4px 12px rgba(3, 4, 6, 0.4)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'toast-in': {
          from: { opacity: '0', transform: 'translateX(8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.24s ease-out',
        'toast-in': 'toast-in 0.2s ease-out',
      },
    },
  },
  plugins: [],
} satisfies Config
