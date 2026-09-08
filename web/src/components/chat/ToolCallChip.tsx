import { useState } from 'react'

type ToolCallChipProps = {
  tool: string
  input: unknown
  result: string
  isError: boolean
}

export function ToolCallChip({ tool, input, result, isError }: ToolCallChipProps) {
  const [expanded, setExpanded] = useState(false)
  const summary = result.length > 80 ? `${result.slice(0, 80)}…` : result

  return (
    <div
      className={`rounded-lg border text-xs ${isError ? 'border-failed/40 bg-failed/5' : 'border-border bg-surface'}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        aria-expanded={expanded}
      >
        <span className={`font-mono ${isError ? 'text-failed' : 'text-accent'}`}>{tool}</span>
        <span className="truncate text-text-muted">{summary}</span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className={`ml-auto h-3.5 w-3.5 shrink-0 text-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {expanded && (
        <div className="border-t border-border px-3 py-2">
          <div className="mb-1 font-medium text-text-faint">Input</div>
          <pre className="mb-2 overflow-x-auto whitespace-pre-wrap break-words font-mono text-text">
            {JSON.stringify(input, null, 2)}
          </pre>
          <div className="mb-1 font-medium text-text-faint">Result</div>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-text">{result}</pre>
        </div>
      )}
    </div>
  )
}
