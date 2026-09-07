export type AlertSeverity = 'warning' | 'critical'

export type Alert = {
  id: number
  deployment_id: number
  service_id: number
  severity: AlertSeverity
  title: string
  description: string | null
  fired_at: string
  resolved_at: string | null
  alertmanager_id: string | null
}
