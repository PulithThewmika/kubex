import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '../../lib/apiFetch'
import { CodeBlock } from '../CodeBlock'
import { RadioCards, type RadioOption } from './RadioCards'

export type DeployMethod = 'argocd' | 'github' | 'webhook' | 'skip'

const OPTIONS: RadioOption[] = [
  { value: 'argocd', label: 'ArgoCD', description: 'Connect a cluster running the KubeX agent — it watches ArgoCD syncs.' },
  { value: 'github', label: 'GitHub Deployments', description: 'Use GitHub deployment statuses from the App you just installed. Nothing else to configure.' },
  { value: 'webhook', label: 'Deploy webhook', description: 'Call the KubeX API from your own pipeline with an org API key.' },
  { value: 'skip', label: 'Skip for now', description: "Decide later — you can set this up from Settings any time." },
]

async function createApiKey(name: string): Promise<{ token: string }> {
  const res = await apiFetch('/api/settings/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Failed to create API key: ${res.status}`)
  }
  return res.json()
}

function curlExample(ingestUrl: string, token: string): string {
  return [
    `curl -X POST ${ingestUrl}/api/deployments/notify \\`,
    `  -H "Authorization: Bearer ${token}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{"service": "my-service", "commit_sha": "'"$GIT_SHA"'", "status": "success"}'`,
  ].join('\n')
}

type DeployMethodStepProps = {
  value: DeployMethod | null
  onChange: (value: DeployMethod) => void
  onAddCluster: () => void
  ingestPublicUrl: string | undefined
}

export function DeployMethodStep({ value, onChange, onAddCluster, ingestPublicUrl }: DeployMethodStepProps) {
  const keyMutation = useMutation({ mutationFn: createApiKey })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-xl font-semibold text-text">How do you deploy?</h2>
        <p className="text-sm text-text-muted">
          KubeX correlates each release across CI and CD. Tell us where your deploys come from.
        </p>
      </div>

      <RadioCards
        legend="Deployment method"
        name="deploy-method"
        options={OPTIONS}
        value={value}
        onChange={(v) => onChange(v as DeployMethod)}
      >
        {value === 'argocd' && (
          <button
            type="button"
            onClick={onAddCluster}
            className="w-fit rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-surface"
          >
            Add a cluster
          </button>
        )}
        {value === 'github' && (
          <p className="text-xs text-text-muted">
            Covered by the GitHub App from step 1 — deployment statuses flow in automatically.
          </p>
        )}
        {value === 'webhook' && (
          <div className="flex flex-col gap-2">
            {!keyMutation.data ? (
              <>
                <button
                  type="button"
                  disabled={keyMutation.isPending}
                  onClick={() => keyMutation.mutate('Onboarding deploy webhook')}
                  className="w-fit rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-surface disabled:opacity-50"
                >
                  {keyMutation.isPending ? 'Generating…' : 'Generate API key'}
                </button>
                {keyMutation.isError && (
                  <p className="text-xs text-failed">{(keyMutation.error as Error).message}</p>
                )}
              </>
            ) : (
              <>
                <p className="text-xs text-text-muted">
                  Copy this key now — it's shown only once. Then call the API from your pipeline:
                </p>
                <CodeBlock code={keyMutation.data.token} />
                <CodeBlock code={curlExample(ingestPublicUrl ?? 'https://your-kubex-host', keyMutation.data.token)} />
              </>
            )}
          </div>
        )}
      </RadioCards>
    </div>
  )
}
