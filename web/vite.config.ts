import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/install': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Slack OAuth connect + Events webhook (E23-T5) — the "Add to Slack"
      // link is a top-level <a href="/integrations/slack/install">.
      '/integrations': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/webhooks': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/grafana': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/grafana/, ''),
      },
    },
  },
})
