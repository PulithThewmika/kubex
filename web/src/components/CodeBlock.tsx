import { useEffect, useRef, useState } from 'react'

type CodeBlockProps = {
  code: string
}

const COPIED_RESET_MS = 2000

export function CodeBlock({ code }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimer.current) clearTimeout(resetTimer.current)
    }
  }, [])

  async function handleCopy() {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    if (resetTimer.current) clearTimeout(resetTimer.current)
    resetTimer.current = setTimeout(() => setCopied(false), COPIED_RESET_MS)
  }

  return (
    <div className="relative border-2 border-text bg-background">
      <button
        type="button"
        onClick={handleCopy}
        className="absolute right-2 top-2 border-2 border-text-muted px-2.5 py-1 font-body text-[0.65rem] font-bold uppercase tracking-widest text-text-muted transition-colors hover:border-accent hover:text-accent"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="overflow-x-auto p-4 pr-20 font-mono text-xs leading-relaxed text-text">
        <code>{code}</code>
      </pre>
    </div>
  )
}
