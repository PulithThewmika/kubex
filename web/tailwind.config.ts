import type { Config } from 'tailwindcss'

// KubeX design system — dark-tech observability.
// Direction: a single cool-tinted near-black surface ladder (not pure black),
// the brand orange as the one accent, and a GitHub-Primer-adjacent status
// palette (green/amber/red/blue) that the SRE audience already reads fluently
// and that clears WCAG AA on the dark surfaces. Dark-only by design — dark is
// the product's identity, not a mode.
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

        // The one accent.
        accent: '#F97316',
        'accent-hover': '#FB9A4B',

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
