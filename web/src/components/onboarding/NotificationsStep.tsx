import { useSlackConnection } from '../../hooks/useSlack'

function SlackIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M6 15a2 2 0 1 1-2-2h2v2Zm1 0a2 2 0 0 1 4 0v5a2 2 0 0 1-4 0v-5Zm2-8a2 2 0 1 1 2-2v2H9Zm0 1a2 2 0 0 1 0 4H4a2 2 0 0 1 0-4h5Zm8 2a2 2 0 1 1 2 2h-2v-2Zm-1 0a2 2 0 0 1-4 0V4a2 2 0 0 1 4 0v5Zm-2 8a2 2 0 1 1-2 2v-2h2Zm0-1a2 2 0 0 1 0-4h5a2 2 0 0 1 0 4h-5Z" />
    </svg>
  )
}

export function NotificationsStep() {
  const { data } = useSlackConnection()
  const connected = data?.connected ?? false

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-xl font-semibold text-text">Get deploy alerts in Slack</h2>
        <p className="text-sm text-text-muted">
          When a deployment degrades or fails, KubeX can post the health score and evidence straight to a
          Slack channel. Entirely optional — you can connect it later from Settings.
        </p>
      </div>

      {connected ? (
        <div
          role="status"
          className="rounded-lg border border-healthy/30 bg-healthy/10 px-4 py-3 text-sm text-healthy"
        >
          Connected to {data?.team_name ?? 'your workspace'}. Pick channels to notify from Settings →
          Connections.
        </div>
      ) : (
        <a
          href="/integrations/slack/install"
          className="flex w-fit items-center gap-2 rounded-md bg-text px-4 py-2.5 text-sm font-medium text-background transition-colors hover:opacity-90"
        >
          <SlackIcon />
          Add to Slack
        </a>
      )}

      <p className="text-xs text-text-muted">
        Opens Slack in this tab and returns you to Settings when the install completes.
      </p>
    </div>
  )
}
