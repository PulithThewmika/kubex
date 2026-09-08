export type Cluster = {
  id: string
  name: string
  status: 'pending' | 'connected' | 'disconnected'
  agent_version: string | null
  argocd_version: string | null
  argocd_status: string | null
  prometheus_status: string | null
  last_heartbeat: string | null
  created_at: string
}

export type ClusterCreateResponse = {
  id: string
  name: string
  token: string
  created_at: string
}

export type ClusterRotateTokenResponse = {
  token: string
  grace_period_expires_at: string
}
