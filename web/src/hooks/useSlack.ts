import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiFetch'
import type { SlackChannel, SlackConnection, SlackPickerChannel } from '../types/slack'

const SLACK_QUERY_KEY = ['slack-connection']

async function fetchConnection(): Promise<SlackConnection> {
  const res = await apiFetch('/api/settings/slack')
  if (!res.ok) throw new Error(`Failed to load Slack connection: ${res.status}`)
  return res.json()
}

async function detail(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null)
  return body?.detail ?? fallback
}

export function useSlackConnection() {
  return useQuery({ queryKey: SLACK_QUERY_KEY, queryFn: fetchConnection })
}

/** Only fetched on demand (picker open) — needs a live Slack API round-trip. */
export function useSlackAvailableChannels(enabled: boolean) {
  return useQuery({
    queryKey: ['slack-available-channels'],
    enabled,
    staleTime: 30_000,
    queryFn: async (): Promise<SlackPickerChannel[]> => {
      const res = await apiFetch('/api/settings/slack/channels/available')
      if (!res.ok) throw new Error(await detail(res, `Failed to list channels: ${res.status}`))
      return res.json()
    },
  })
}

export function useAddSlackChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      slack_channel_id: string
      slack_channel_name: string
      service_id?: number | null
    }): Promise<SlackChannel> => {
      const res = await apiFetch('/api/settings/slack/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await detail(res, `Failed to add channel: ${res.status}`))
      return res.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: SLACK_QUERY_KEY }),
  })
}

export function useRemoveSlackChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const res = await apiFetch(`/api/settings/slack/channels/${id}`, { method: 'DELETE' })
      if (!res.ok && res.status !== 404) throw new Error(`Failed to remove channel: ${res.status}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: SLACK_QUERY_KEY }),
  })
}

export function useTestSlackChannel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const res = await apiFetch(`/api/settings/slack/channels/${id}/test`, { method: 'POST' })
      if (!res.ok) throw new Error(await detail(res, `Test message failed: ${res.status}`))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: SLACK_QUERY_KEY }),
  })
}

export function useDisconnectSlack() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<void> => {
      const res = await apiFetch('/api/settings/slack', { method: 'DELETE' })
      if (!res.ok && res.status !== 404) throw new Error(`Failed to disconnect: ${res.status}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: SLACK_QUERY_KEY }),
  })
}
