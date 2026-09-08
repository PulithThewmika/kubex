import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '../lib/apiFetch'
import { CLUSTERS_QUERY_KEY, fetchClusters } from '../hooks/useClusters'
import { useInstallInfo, type InstallInfo } from '../hooks/useInstallInfo'
import { CodeBlock } from './CodeBlock'
import { Modal } from './Modal'
import type { Cluster, ClusterCreateResponse } from '../types/cluster'

type Step = 'name' | 'token' | 'install' | 'waiting'
type InstallMethod = 'kubectl' | 'helm' | 'gitops'

async function createCluster(name: string): Promise<ClusterCreateResponse> {
  const res = await apiFetch('/api/clusters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Failed to create cluster: ${res.status}`)
  }
  return res.json()
}

// Faster than useClusters()' 30s background poll — this only runs while the
// wizard's "waiting for heartbeat" step is open, so a quick confirmation
// matters more than request volume. Shares useClusters()' own ['clusters']
// query (same queryFn, via `select` to pick out this one cluster) instead of
// polling a separate copy under its own key: while both this hook and
// ClustersSection's useClusters() are mounted, TanStack Query dedupes them
// into one shared request using the shortest active refetchInterval, so the
// wizard's faster cadence also keeps the Settings list underneath fresh
// instead of two independent pollers hitting the same endpoint.
const WAITING_POLL_MS = 3000

function useClusterConnected(clusterId: string | null) {
  return useQuery({
    queryKey: CLUSTERS_QUERY_KEY,
    queryFn: fetchClusters,
    enabled: clusterId !== null,
    select: (clusters) => clusters.find((c) => c.id === clusterId),
    refetchInterval: (query) => {
      const clusters = query.state.data as Cluster[] | undefined
      const cluster = clusters?.find((c) => c.id === clusterId)
      return cluster?.status === 'connected' ? false : WAITING_POLL_MS
    },
  })
}

// Helm release names must be valid DNS-1123 labels (lowercase alphanumeric
// and '-', <=53 chars) — a cluster display name like "My Prod!" is legal
// per the backend's own naming rules but not as a Helm release name,
// producing a command that fails immediately on paste (CodeRabbit, PR
// #804). Deterministic given the same clusterName, so it doesn't need to
// be persisted anywhere — it's just what's suggested in this one command.
function toHelmReleaseName(clusterName: string): string {
  const normalized = clusterName
    .toLowerCase()
    .replaceAll(/[^a-z0-9-]+/g, '-')
    .replaceAll(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 53)
  return normalized || 'cluster-agent'
}

// Namespace/chart repo/chart path come from the backend's own install-info
// endpoint (E22-T5, #806) rather than being duplicated as string literals
// here — those values live authoritatively in install.py, which only the
// kubectl tab (GET /install/:token.yaml) previously read from.
function installCommand(
  method: InstallMethod,
  token: string,
  clusterName: string,
  info: InstallInfo,
): string {
  switch (method) {
    case 'kubectl':
      return `curl -sL ${info.ingest_public_url}/install/${token}.yaml | kubectl apply -f -`
    case 'helm':
      return [
        // Explicit target dir: `git clone <url>` derives the directory
        // name from the URL itself, which happens to be "kubex" for the
        // current repo but silently breaks the next line's `kubex/...`
        // path the moment chart_repo_url points anywhere else — a fork, a
        // rename (CodeRabbit, PR #804).
        `git clone ${info.chart_repo_url} kubex`,
        `helm install ${toHelmReleaseName(clusterName)} kubex/${info.chart_path} \\`,
        `  --create-namespace --namespace ${info.agent_namespace} \\`,
        `  --set token=${token} \\`,
        `  --set endpoint=${info.ingest_public_url} \\`,
        // A literal <placeholder> breaks the shell (< is redirection) if
        // copied as-is (CodeRabbit, PR #804) — REPLACE_WITH_SHA is a plain
        // token that runs (and fails clearly on a nonexistent tag) rather
        // than erroring on paste, while still being unmistakably something
        // to edit first.
        '  --set image.tag=REPLACE_WITH_SHA  # find the latest tag at https://github.com/PulithThewmika/kubex/pkgs/container/kubex-cluster-agent',
      ].join('\n')
    case 'gitops':
      // Unlike the kubectl/Helm one-liners (run once, never persisted), this
      // snippet is meant to be committed into the customer's own GitOps
      // repo — embedding the real token here would put it in plaintext Git
      // history. Keep it a placeholder, same as deploy/argocd/cluster-agent.yaml's
      // own committed example, and point at the token already shown in the
      // previous step instead.
      return [
        `# Copy deploy/argocd/cluster-agent.yaml from the kubex repo into your`,
        '# GitOps repo, then set its placeholders — route the token through',
        "# your existing secrets tooling (Sealed Secrets, Vault, etc.), don't",
        '# commit it in plaintext:',
        `#   token: <the token shown in the previous step>`,
        `#   endpoint: "${info.ingest_public_url}"`,
        '#   image.tag: "<latest short-SHA tag from the ghcr.io package page>"',
      ].join('\n')
  }
}

const INSTALL_TABS: { id: InstallMethod; label: string }[] = [
  { id: 'kubectl', label: 'kubectl' },
  { id: 'helm', label: 'Helm' },
  { id: 'gitops', label: 'GitOps' },
]

type AddClusterModalProps = {
  onClose: () => void
}

export function AddClusterModal({ onClose }: AddClusterModalProps) {
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [installMethod, setInstallMethod] = useState<InstallMethod>('kubectl')
  const [created, setCreated] = useState<ClusterCreateResponse | null>(null)
  const queryClient = useQueryClient()
  const { data: installInfo, isError: installInfoError, refetch: retryInstallInfo } = useInstallInfo()

  const createMutation = useMutation({
    mutationFn: createCluster,
    onSuccess: (data) => {
      setCreated(data)
      setStep('token')
      queryClient.invalidateQueries({ queryKey: CLUSTERS_QUERY_KEY })
    },
  })

  const {
    data: waitingCluster,
    isError: waitingError,
    refetch: retryWaiting,
  } = useClusterConnected(step === 'waiting' && created ? created.id : null)
  const connected = waitingCluster?.status === 'connected'

  function handleClose() {
    // The token is shown exactly once (onSuccess below) — closing mid-create
    // would let the mutation resolve after unmount and lose it, leaving a
    // cluster row with no way to see its token again (CodeRabbit, PR #804).
    if (createMutation.isPending) return
    onClose()
  }

  return (
    <Modal titleId="add-cluster-title" title="Add cluster" onClose={handleClose}>
      {step === 'name' && (
        <div className="mt-4 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-text">Cluster name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="production"
              autoFocus
              className="rounded-md border border-border-strong bg-background px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            />
          </label>
          {createMutation.isError && (
            <p className="text-sm text-failed">{(createMutation.error as Error).message}</p>
          )}
          <button
            type="button"
            disabled={name.trim().length === 0 || createMutation.isPending}
            onClick={() => createMutation.mutate(name.trim())}
            className="w-fit rounded-md bg-accent px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating…' : 'Continue'}
          </button>
        </div>
      )}

      {step === 'token' && created && (
        <div className="mt-4 flex flex-col gap-4">
          <p className="text-sm text-text-muted">
            This token authenticates the agent to KubeX. It's shown only once — copy it now, or you'll need to
            rotate it to get a new one.
          </p>
          <CodeBlock code={created.token} />
          <button
            type="button"
            onClick={() => setStep('install')}
            className="w-fit rounded-md bg-accent px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-accent-hover active:translate-y-px"
          >
            Continue
          </button>
        </div>
      )}

      {step === 'install' && created && (
        <div className="mt-4 flex flex-col gap-4">
          <div className="flex gap-1 border-b border-border">
            {INSTALL_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setInstallMethod(tab.id)}
                className={`px-3 py-2 text-sm font-medium transition-colors ${
                  installMethod === tab.id ? 'border-b-2 border-accent text-text' : 'text-text-muted hover:text-text'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {installInfo ? (
            <CodeBlock code={installCommand(installMethod, created.token, name.trim(), installInfo)} />
          ) : installInfoError ? (
            <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background p-3">
              <p className="text-sm text-failed">Couldn't load install instructions.</p>
              <button
                type="button"
                onClick={() => retryInstallInfo()}
                className="w-fit rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-background"
              >
                Retry
              </button>
            </div>
          ) : (
            <p className="text-sm text-text-muted">Loading install instructions…</p>
          )}
          <button
            type="button"
            onClick={() => setStep('waiting')}
            disabled={!installInfo}
            className="w-fit rounded-md bg-accent px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:opacity-50"
          >
            I've installed it
          </button>
        </div>
      )}

      {step === 'waiting' && (
        <div className="mt-4 flex flex-col items-center gap-3 py-6 text-center">
          {connected ? (
            <>
              <span className="rounded-full bg-healthy/10 px-3 py-1 text-sm font-medium text-healthy">
                Connected
              </span>
              <p className="text-sm text-text-muted">The agent is reporting heartbeats. You're all set.</p>
              <button
                type="button"
                onClick={handleClose}
                className="mt-2 w-fit rounded-md bg-accent px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-accent-hover active:translate-y-px"
              >
                Done
              </button>
            </>
          ) : waitingError ? (
            <>
              <p className="text-sm text-failed">Couldn't check the cluster's status.</p>
              <button
                type="button"
                onClick={() => retryWaiting()}
                className="w-fit rounded-md border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-background"
              >
                Retry
              </button>
            </>
          ) : (
            <>
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" />
              <p className="text-sm text-text-muted">Waiting for the agent's first heartbeat…</p>
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
