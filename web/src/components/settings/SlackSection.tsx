import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useAddSlackChannel,
  useDisconnectSlack,
  useRemoveSlackChannel,
  useSlackAvailableChannels,
  useSlackConnection,
  useTestSlackChannel,
} from '../../hooks/useSlack'
import type { SlackChannel } from '../../types/slack'
import { StatusBadge } from '../StatusBadge'

const INSTALL_URL = '/integrations/slack/install'

function SlackIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M6 15a2 2 0 1 1-2-2h2v2Zm1 0a2 2 0 0 1 4 0v5a2 2 0 0 1-4 0v-5Zm2-8a2 2 0 1 1 2-2v2H9Zm0 1a2 2 0 0 1 0 4H4a2 2 0 0 1 0-4h5Zm8 2a2 2 0 1 1 2 2h-2v-2Zm-1 0a2 2 0 0 1-4 0V4a2 2 0 0 1 4 0v5Zm-2 8a2 2 0 1 1-2 2v-2h2Zm0-1a2 2 0 0 1 0-4h5a2 2 0 0 1 0 4h-5Z" />
    </svg>
  )
}

function DeliveryStatus({ channel }: { channel: SlackChannel }) {
  if (!channel.enabled) {
    return <StatusBadge variant="failed">disabled</StatusBadge>
  }
  if (channel.last_delivery_error) {
    return (
      <span
        className="font-body text-xs font-bold uppercase tracking-wide text-degraded"
        title={channel.last_delivery_error}
      >
        Last delivery failed: {channel.last_delivery_error}
      </span>
    )
  }
  if (channel.last_delivery_at) {
    return <span className="font-body text-xs font-bold uppercase tracking-wide text-healthy">Delivering</span>
  }
  return (
    <span className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
      No messages sent yet
    </span>
  )
}

function ChannelRow({ channel }: { channel: SlackChannel }) {
  const remove = useRemoveSlackChannel()
  const test = useTestSlackChannel()
  return (
    <li className="flex flex-col gap-2 border-2 border-paper-line-soft bg-paper-raised p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <p className="font-body text-sm font-bold text-ink">#{channel.slack_channel_name}</p>
        <DeliveryStatus channel={channel} />
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => test.mutate(channel.id)}
          disabled={test.isPending}
          className="border-2 border-ink-muted px-2.5 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-ink transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
        >
          {test.isPending ? 'Sending…' : 'Send test'}
        </button>
        <button
          type="button"
          onClick={() => remove.mutate(channel.id)}
          disabled={remove.isPending}
          className="border-2 border-transparent px-2.5 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-failed transition-colors hover:border-failed disabled:opacity-50"
        >
          Remove
        </button>
      </div>
      {(test.isError || remove.isError) && (
        <p className="font-body text-xs font-bold uppercase tracking-wide text-failed sm:w-full" role="alert">
          {((test.error ?? remove.error) as Error).message}
        </p>
      )}
    </li>
  )
}

function AddChannel({ existingIds }: { existingIds: Set<string> }) {
  const [open, setOpen] = useState(false)
  const available = useSlackAvailableChannels(open)
  const add = useAddSlackChannel()

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-fit border-2 border-ink-muted px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-ink transition-colors hover:border-accent hover:text-accent"
      >
        Add a channel
      </button>
    )
  }

  const choices = (available.data ?? []).filter((c) => !existingIds.has(c.slack_channel_id))

  return (
    <div className="flex flex-col gap-2">
      {available.isLoading && (
        <p className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Loading channels…
        </p>
      )}
      {available.isError && (
        <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
          {(available.error as Error).message}
        </p>
      )}
      {available.data && (
        <ul className="flex flex-col gap-1.5">
          {choices.map((c) => (
            <li key={c.slack_channel_id} className="flex items-center justify-between gap-2">
              <span className="font-body text-sm text-ink">
                #{c.name}
                {c.is_private && !c.is_member && (
                  <span className="ml-2 font-body text-xs font-bold uppercase tracking-wide text-degraded">
                    invite @KubeX first
                  </span>
                )}
              </span>
              <button
                type="button"
                onClick={() =>
                  add.mutate(
                    { slack_channel_id: c.slack_channel_id, slack_channel_name: c.name, service_id: null },
                    { onSuccess: () => setOpen(false) },
                  )
                }
                disabled={add.isPending}
                className="border-2 border-ink-muted px-2.5 py-1 font-body text-xs font-bold uppercase tracking-wide text-ink transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
              >
                Add
              </button>
            </li>
          ))}
          {choices.length === 0 && (
            <li className="font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
              No more channels the bot can see.
            </li>
          )}
        </ul>
      )}
      {add.isError && (
        <p className="font-body text-xs font-bold uppercase tracking-wide text-failed" role="alert">
          {(add.error as Error).message}
        </p>
      )}
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="w-fit font-body text-xs font-bold uppercase tracking-wide text-ink-muted underline-offset-4 hover:text-accent hover:underline"
      >
        Cancel
      </button>
    </div>
  )
}

export function SlackSection() {
  const [searchParams] = useSearchParams()
  const slackParam = searchParams.get('slack')
  const { data, isLoading, isError } = useSlackConnection()
  const disconnect = useDisconnectSlack()

  return (
    <section className="mt-10">
      <h2 className="font-body text-xs font-bold uppercase tracking-[0.15em] text-ink-muted">Slack</h2>
      <p className="mt-1 font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Get deploy health alerts in your own Slack workspace. Optional — deployments are still tracked
        without it.
      </p>

      {slackParam === 'connected' && (
        <div role="status" className="mt-4 border-2 border-healthy bg-healthy/10 px-4 py-3 font-body text-xs font-bold uppercase tracking-wide text-healthy">
          Slack workspace connected.
        </div>
      )}
      {slackParam === 'denied' && (
        <div role="status" className="mt-4 border-2 border-degraded bg-degraded/10 px-4 py-3 font-body text-xs font-bold uppercase tracking-wide text-degraded">
          Slack authorization was cancelled.
        </div>
      )}
      {slackParam === 'exists' && (
        <div role="status" className="mt-4 border-2 border-degraded bg-degraded/10 px-4 py-3 font-body text-xs font-bold uppercase tracking-wide text-degraded">
          A Slack workspace is already connected. Disconnect it before connecting a different one.
        </div>
      )}

      {isLoading && (
        <p className="mt-4 font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">Loading…</p>
      )}
      {isError && (
        <p className="mt-4 font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Slack integration is unavailable on this server.
        </p>
      )}

      {data && !data.connected && (
        <a
          href={INSTALL_URL}
          className="mt-4 flex w-fit items-center gap-2 border-2 border-accent bg-accent px-4 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px"
        >
          <SlackIcon />
          Add to Slack
        </a>
      )}

      {data && data.connected && (
        <div className="mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-body text-sm text-ink">
              Connected to <span className="font-bold">{data.team_name ?? 'your workspace'}</span>
            </p>
            <button
              type="button"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
              className="font-body text-xs font-bold uppercase tracking-wide text-failed underline-offset-4 hover:underline disabled:opacity-50"
            >
              Disconnect
            </button>
          </div>

          {disconnect.isError && (
            <p className="font-body text-xs font-bold uppercase tracking-wide text-failed" role="alert">
              {(disconnect.error as Error).message}
            </p>
          )}

          {data.channels.length > 0 && (
            <ul className="flex flex-col gap-2">
              {data.channels.map((c) => (
                <ChannelRow key={c.id} channel={c} />
              ))}
            </ul>
          )}

          <AddChannel existingIds={new Set(data.channels.map((c) => c.slack_channel_id))} />
        </div>
      )}
    </section>
  )
}
