import { useState } from 'react'
import { ChatWindow } from '../components/chat/ChatWindow'
import { useChatSession } from '../hooks/useChatSession'

const SUGGESTED_PROMPTS = [
  'What deployed today?',
  'Why is $service degraded?',
  'Compare the last two deploys of $service',
]

export function Chat() {
  const { messages, isStreaming, error, sendMessage } = useChatSession()
  const [input, setInput] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    setInput('')
    void sendMessage(trimmed)
  }

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div role="alert" className="border-b-2 border-failed bg-failed/10 px-4 py-2 font-body text-xs font-bold uppercase tracking-wide text-failed">
          {error}
        </div>
      )}
      {messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
          <div className="flex h-11 w-11 items-center justify-center border-2 border-paper-line-soft bg-paper-raised text-accent">
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
              <path
                d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9A1.5 1.5 0 0 1 18.5 16H9l-4 4v-4H5.5A1.5 1.5 0 0 1 4 14.5v-9Z"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <p className="font-heading text-lg font-bold uppercase tracking-tight text-ink">
              Ask about your deployments
            </p>
            <p className="mt-1 max-w-sm font-body text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Grounded in your real correlation, health, and metrics history.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setInput(prompt)}
                className="border-2 border-paper-line-soft px-3 py-1.5 font-body text-xs font-bold uppercase tracking-wide text-ink-muted transition-colors hover:border-accent hover:text-accent"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <ChatWindow messages={messages} isStreaming={isStreaming} />
      )}
      <form onSubmit={handleSubmit} className="flex gap-2 border-t-2 border-paper-line p-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isStreaming}
          placeholder="Ask about a deployment, service, or incident…"
          className="flex-1 border-2 border-paper-line-soft bg-paper-raised px-3.5 py-2.5 font-body text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          className="border-2 border-accent bg-accent px-5 py-2.5 font-body text-xs font-bold uppercase tracking-wide text-background transition-colors hover:bg-accent-hover active:translate-y-px disabled:opacity-50 disabled:border-paper-line-soft disabled:bg-paper-line-soft"
        >
          Send
        </button>
      </form>
    </div>
  )
}
