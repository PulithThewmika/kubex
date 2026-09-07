export type SlackChannel = {
  id: string
  slack_channel_id: string
  slack_channel_name: string
  service_id: number | null
  event_types: string[]
  enabled: boolean
  last_delivery_at: string | null
  last_delivery_error: string | null
}

export type SlackConnection = {
  connected: boolean
  workspace_id: string | null
  team_name: string | null
  channels: SlackChannel[]
}

export type SlackPickerChannel = {
  slack_channel_id: string
  name: string
  is_private: boolean
  is_member: boolean
}
