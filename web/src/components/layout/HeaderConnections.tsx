import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useInstallations } from '../../hooks/useInstallations'
import { useSlackConnection } from '../../hooks/useSlack'

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.5 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.46-1.19-1.11-1.51-1.11-1.51-.91-.64.07-.63.07-.63 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.31.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 2.5-.35c.85 0 1.7.12 2.5.35 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .28.18.61.69.5A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  )
}

function SlackIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M6 15a2 2 0 1 1-2-2h2v2Zm1 0a2 2 0 0 1 4 0v5a2 2 0 0 1-4 0v-5ZM9 6a2 2 0 1 1 2-2v2H9Zm0 1a2 2 0 0 1 0 4H4a2 2 0 0 1 0-4h5Zm9 2a2 2 0 1 1 2 2h-2V9Zm-1 0a2 2 0 0 1-4 0V4a2 2 0 0 1 4 0v5Zm-2 9a2 2 0 1 1-2 2v-2h2Zm0-1a2 2 0 0 1 0-4h5a2 2 0 0 1 0 4h-5Z" />
    </svg>
  )
}

function StatusIcon({ label, connected, children }: { label: string; connected: boolean; children: ReactNode }) {
  return (
    <Link
      to="/app/settings?tab=connections"
      title={`${label}: ${connected ? 'connected' : 'not connected'}`}
      aria-label={`${label} ${connected ? 'connected' : 'not connected'} — open connection settings`}
      className="relative flex h-8 w-8 items-center justify-center text-background/70 transition-colors hover:text-background"
    >
      {children}
      <span
        className={`absolute right-0 top-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-text ${
          connected ? 'bg-healthy' : 'bg-failed'
        }`}
        aria-hidden="true"
      />
    </Link>
  )
}

export function HeaderConnections() {
  const { data: installations } = useInstallations()
  const { data: slack } = useSlackConnection()
  const githubConnected = Boolean(installations?.some((i) => i.status === 'active'))
  const slackConnected = Boolean(slack?.connected)

  return (
    <div className="flex items-center gap-1">
      <StatusIcon label="GitHub" connected={githubConnected}>
        <GitHubIcon />
      </StatusIcon>
      <StatusIcon label="Slack" connected={slackConnected}>
        <SlackIcon />
      </StatusIcon>
    </div>
  )
}
