import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '../lib/apiFetch'
import { CodeBlock } from './CodeBlock'
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
// matters more than request volume.
const WAITING_POLL_MS = 3000

function useClusterConnected(clusterId: string | null) {
  return useQuery({
    queryKey: ['clusters', 'waiting', clusterId],
    queryFn: async (): Promise<Cluster> => {
      const res = await apiFetch('/api/clusters')
      if (!res.ok) throw new Error(`Failed to fetch clusters: ${res.status}`)
      const clusters: Cluster[] = await res.json()
      const cluster = clusters.find((c) => c.id === clusterId)
      if (!cluster) throw new Error('Cluster not found')
      return cluster
    },
    enabled: clusterId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'connected' ? false : WAITING_POLL_MS),
  })
}

function installCommand(method: InstallMethod, token: string, endpoint: string, clusterName: string): string {
  switch (method) {
    case 'kubectl':
      return `curl -sL ${endpoint}/install/${token}.yaml | kubectl apply -f -`
    case 'helm':
      return [
        'git clone https://github.com/PulithThewmika/kubex.git',
        `helm install ${clusterName} kubex/deploy/helm/cluster-agent \\`,
        '  --create-namespace --namespace kubex-agent \\',
        `  --set token=${token} \\`,
        `  --set endpoint=${endpoint} \\`,
        '  --set image.tag=<latest short-SHA tag from the ghcr.io package page>',
      ].join('\n')
    case 'gitops':
      // Unlike the kubectl/Helm one-liners (run once, never persisted), this
      // snippet is meant to be committed into the customer's own GitOps
      // repo — embedding the real token here would put it in plaintext Git
      // history. Keep it a placeholder, same as deploy/argocd/cluster-agent.yaml's
      // own committed example, and point at the token already shown in the
      // previous step instead.
      return [
        '# Copy deploy/argocd/cluster-agent.yaml from the kubex repo into your',
        '# GitOps repo, then set its placeholders — route the token through',
        "# your existing secrets tooling (Sealed Secrets, Vault, etc.), don't",
        '# commit it in plaintext:',
        `#   token: <the token shown in the previous step>`,
        `#   endpoint: "${endpoint}"`,
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

  const createMutation = useMutation({
    mutationFn: createCluster,
    onSuccess: (data) => {
      setCreated(data)
      setStep('token')
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
  })

  const { data: waitingCluster } = useClusterConnected(step === 'waiting' && created ? created.id : null)
  const connected = waitingCluster?.status === 'connected'

  function handleClose() {
    queryClient.invalidateQueries({ queryKey: ['clusters'] })
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && handleClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-cluster-title"
        className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-y-auto rounded-lg border border-border bg-surface p-6"
      >
        <div className="flex items-center justify-between">
          <h2 id="add-cluster-title" className="font-heading text-lg font-semibold text-text">
            Add cluster
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="text-text-muted hover:text-text"
          >
            ✕
          </button>
        </div>

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
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-text"
              />
            </label>
            {createMutation.isError && (
              <p className="text-sm text-failed">{(createMutation.error as Error).message}</p>
            )}
            <button
              type="button"
              disabled={name.trim().length === 0 || createMutation.isPending}
              onClick={() => createMutation.mutate(name.trim())}
              className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:opacity-50"
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
              className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
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
                    installMethod === tab.id
                      ? 'border-b-2 border-accent text-text'
                      : 'text-text-muted hover:text-text'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <CodeBlock code={installCommand(installMethod, created.token, window.location.origin, name.trim())} />
            <button
              type="button"
              onClick={() => setStep('waiting')}
              className="w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
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
                  className="mt-2 w-fit rounded-md bg-text px-4 py-2 text-sm font-medium text-background transition-colors hover:opacity-90"
                >
                  Done
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
      </div>
    </div>
  )
}
