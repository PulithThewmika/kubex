import { useState } from 'react'
import { CodeBlock } from '../CodeBlock'

// /mcp is proxied to the backend by vercel.json, so this stays same-origin
// instead of hardcoding the backend host. Override via VITE_MCP_URL for
// setups where that rewrite doesn't apply (e.g. local dev against a remote backend).
const MCP_URL = import.meta.env.VITE_MCP_URL ?? `${window.location.origin}/mcp`

type Client = 'claude' | 'chatgpt'

function ClaudeSteps() {
  return (
    <ol className="flex flex-col gap-2 text-sm text-text-muted">
      <li>1. In Claude (Desktop or claude.ai), go to Settings → Connectors → Add custom connector.</li>
      <li>2. Paste the server URL above.</li>
      <li>
        3. Under Authentication, choose <span className="font-medium text-text">None</span> — KubeX
        uses a static API key, not Claude's OAuth flow.
      </li>
      <li>
        4. Under Additional request headers, add{' '}
        <span className="font-mono text-xs text-text">Authorization</span> with value{' '}
        <span className="font-mono text-xs text-text">Bearer &lt;your API key&gt;</span>.
      </li>
      <li>5. Save, then ask Claude something like "Using KubeX, what deployments are unhealthy right now?"</li>
    </ol>
  )
}

function ChatGptSteps() {
  return (
    <ol className="flex flex-col gap-2 text-sm text-text-muted">
      <li>1. In ChatGPT, go to Settings → Connectors → Create (requires Plus, Team, or Enterprise).</li>
      <li>2. Set the MCP server URL to the address above.</li>
      <li>
        3. Set Authentication to API Key / Bearer token, and paste your API key as the value. If
        ChatGPT only exposes a raw headers field, add{' '}
        <span className="font-mono text-xs text-text">Authorization</span> with value{' '}
        <span className="font-mono text-xs text-text">Bearer &lt;your API key&gt;</span> instead.
      </li>
      <li>4. Enable the KubeX connector in a chat's tools menu, then ask a question about your deployments.</li>
    </ol>
  )
}

export function McpConnectGuide() {
  const [client, setClient] = useState<Client>('claude')

  return (
    <section className="mt-8 border-t border-border pt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
        Connect Claude or ChatGPT
      </h3>
      <p className="mt-1 text-sm text-text-muted">
        Use any API key above as a bearer token to let Claude or ChatGPT query your org's live
        deployment data directly — the same way you'd connect a remote GitHub MCP server.
      </p>

      <div className="mt-4">
        <span className="text-xs font-medium text-text-muted">Server URL</span>
        <div className="mt-1.5">
          <CodeBlock code={MCP_URL} />
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => setClient('claude')}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            client === 'claude'
              ? 'bg-accent text-background'
              : 'border border-border text-text hover:bg-background'
          }`}
        >
          Claude
        </button>
        <button
          type="button"
          onClick={() => setClient('chatgpt')}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            client === 'chatgpt'
              ? 'bg-accent text-background'
              : 'border border-border text-text hover:bg-background'
          }`}
        >
          ChatGPT
        </button>
      </div>

      <div className="mt-4 rounded-lg border border-border bg-surface p-4">
        {client === 'claude' ? <ClaudeSteps /> : <ChatGptSteps />}
      </div>
    </section>
  )
}
