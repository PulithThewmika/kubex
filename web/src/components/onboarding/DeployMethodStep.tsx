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
  ingestUrlLoading: boolean
  ingestUrlError: boolean
  // Lifted to the page: this step unmounts on navigation, and the token is
  // shown exactly once — losing it would strand a real (unusable) API key on
  // the org and let repeat visits pile up more.
  apiKey: string | null
  onApiKeyCreated: (token: string) => void
}

export function DeployMethodStep({
  value,
  onChange,
  onAddCluster,
  ingestPublicUrl,
  ingestUrlLoading,
  ingestUrlError,
  apiKey,
  onApiKeyCreated,
}: DeployMethodStepProps) {
  const keyMutation = useMutation({ mutationFn: createApiKey, onSuccess: (data) => onApiKeyCreated(data.token) })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-3xl uppercase leading-none text-text sm:text-4xl">How do you deploy?</h2>
        <p className="max-w-md font-body text-sm font-semibold uppercase leading-relaxed tracking-wide text-text-muted">
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
            className="w-fit border-2 border-text-muted px-3.5 py-2 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent"
          >
            Add a cluster
          </button>
        )}
        {value === 'github' && (
          <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
            Covered by the GitHub App from step 1 — deployment statuses flow in automatically.
          </p>
        )}
        {value === 'webhook' && (
          <div className="flex flex-col gap-3">
            {ingestUrlError ? (
              <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
                Couldn't load this org's ingest URL, so the webhook command can't be built yet. Retry in
                a moment or finish setup and add the webhook later.
              </p>
            ) : !apiKey ? (
              <>
                <button
                  type="button"
                  disabled={keyMutation.isPending || ingestUrlLoading || !ingestPublicUrl}
                  onClick={() => keyMutation.mutate('Onboarding deploy webhook')}
                  className="w-fit border-2 border-text-muted px-3.5 py-2 font-body text-xs font-bold uppercase tracking-wide text-text transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {keyMutation.isPending
                    ? 'Generating…'
                    : ingestUrlLoading
                      ? 'Loading…'
                      : 'Generate API key'}
                </button>
                {keyMutation.isError && (
                  <p className="font-body text-xs font-bold uppercase tracking-wide text-failed">
                    {(keyMutation.error as Error).message}
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="font-body text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Copy this key now — it's shown only once. Then call the API from your pipeline:
                </p>
                <CodeBlock code={apiKey} />
                {ingestPublicUrl && <CodeBlock code={curlExample(ingestPublicUrl, apiKey)} />}
              </>
            )}
          </div>
        )}
      </RadioCards>
    </div>
  )
}
