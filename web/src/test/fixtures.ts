import { vi } from 'vitest'
import type { Service } from '../types/service'
import type { DeploymentDetail } from '../types/deploymentDetail'
import type { Installation } from '../types/installation'
import type { Cluster } from '../types/cluster'
import type { Alert } from '../types/alert'

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

export function stubRoutedFetch(routes: Record<string, () => Response>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input.toString()
      for (const [prefix, respond] of Object.entries(routes)) {
        if (url.startsWith(prefix)) return Promise.resolve(respond())
      }
      return Promise.resolve(new Response(null, { status: 404 }))
    }),
  )
}

export function makeService(overrides: Partial<Service> = {}): Service {
  return {
    id: 1,
    name: 'orders',
    namespace: 'kubex',
    repo: 'org/orders',
    argocd_app: 'orders',
    latest_deploy: {
      commit_sha: 'abc123def',
      author: 'alice',
      status: 'deployed',
      finished_at: '2026-08-29T10:00:00Z',
    },
    health: { score: 92, verdict: 'healthy' },
    active_alert_count: 0,
    deploy_count_30d: 4,
    cluster_id: null,
    cluster_name: null,
    integration_status: {
      ci: true,
      cd: 'argocd',
      metrics: 'prometheus',
      available_features: [],
    },
    ...overrides,
  }
}

export function makeDeploymentDetail(overrides: Partial<DeploymentDetail> = {}): DeploymentDetail {
  return {
    id: 42,
    service_id: 1,
    commit_sha: 'abc123def',
    branch: 'main',
    author: 'alice',
    status: 'deployed',
    image_tag: 'v1.2.3',
    started_at: '2026-08-29T09:55:00Z',
    finished_at: '2026-08-29T10:00:00Z',
    commit_at: '2026-08-29T09:50:00Z',
    build_status: 'completed',
    build_duration_s: 60,
    sync_status: 'completed',
    workflow_run_id: 100,
    argocd_revision: 'def456',
    created_at: '2026-08-29T09:50:00Z',
    health_assessment: null,
    service: {
      id: 1,
      name: 'orders',
      repo: 'org/orders',
      argocd_app: 'orders',
      namespace: 'kubex',
      created_at: '2026-01-01T00:00:00Z',
    },
    timeline: [],
    health_evidence: [],
    ...overrides,
  }
}

export function makeAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 1,
    deployment_id: 42,
    service_id: 1,
    service_name: 'orders',
    severity: 'critical',
    title: 'Error rate spike on orders',
    description: 'error_rate 0.12 over 5m',
    fired_at: '2026-08-29T10:00:00Z',
    resolved_at: null,
    alertmanager_id: 'am-1',
    ...overrides,
  }
}

export function makeInstallation(overrides: Partial<Installation> = {}): Installation {
  return {
    id: '1',
    github_installation_id: 12345,
    account_login: 'acme-corp',
    repos: ['acme-corp/kubex'],
    status: 'active',
    created_at: '2026-08-29T10:00:00Z',
    ...overrides,
  }
}

export function makeCluster(overrides: Partial<Cluster> = {}): Cluster {
  return {
    id: '1',
    name: 'prod-cluster',
    status: 'connected',
    agent_version: '0.1.0',
    argocd_version: 'v2.11.0',
    argocd_status: 'found',
    prometheus_status: 'found',
    last_heartbeat: '2026-08-29T10:00:00Z',
    created_at: '2026-08-29T09:00:00Z',
    ...overrides,
  }
}
