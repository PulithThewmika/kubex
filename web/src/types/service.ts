export type LatestDeployInfo = {
  commit_sha: string | null
  author: string | null
  status: string
  finished_at: string | null
}

export type HealthSummary = {
  score: number | null
  verdict: string | null
}

export type CDSource = 'argocd' | 'github_deployments' | 'webhook'
export type MetricsSource = 'prometheus' | 'health_check'

export type IntegrationStatus = {
  ci: boolean
  cd: CDSource | null
  metrics: MetricsSource | null
  available_features: string[]
}

export type Service = {
  id: number
  name: string
  namespace: string
  repo: string | null
  argocd_app: string | null
  latest_deploy: LatestDeployInfo | null
  health: HealthSummary | null
  active_alert_count: number
  integration_status: IntegrationStatus
}
