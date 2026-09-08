import { isValidElement } from 'react'
import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CodeBlock } from '../CodeBlock'

type MarkdownProps = {
  children: string
}

/** Pull the raw text out of a <pre><code> subtree for the CodeBlock copy button. */
function codeText(node: ReactNode): string {
  if (typeof node === 'string') return node
  if (Array.isArray(node)) return node.map(codeText).join('')
  if (isValidElement(node)) return codeText((node.props as { children?: ReactNode }).children)
  return ''
}

// Maximalist paper canvas: heavy borders, orange accent for emphasis/links,
// GitHub-fluent tables. Renders GPT-style markdown (**bold**, lists, ###, ```) cleanly.
export function Markdown({ children }: MarkdownProps) {
  return (
    <div className="font-body text-sm leading-relaxed text-ink [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-3">{children}</p>,
          h1: ({ children }) => (
            <h1 className="mb-3 mt-5 font-heading text-xl font-bold uppercase tracking-tight text-ink">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-5 font-heading text-lg font-bold uppercase tracking-tight text-ink">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-4 font-heading text-base font-bold uppercase tracking-tight text-ink">{children}</h3>
          ),
          strong: ({ children }) => <strong className="font-bold text-ink">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="font-semibold text-accent underline decoration-2 underline-offset-2 hover:text-accent-hover"
            >
              {children}
            </a>
          ),
          ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-5 marker:text-accent">{children}</ul>,
          ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-5 marker:text-ink-muted">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-4 border-accent bg-paper-raised py-1 pl-4 text-ink-muted">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-5 border-t-2 border-paper-line-soft" />,
          pre: ({ children }) => <div className="my-3">{<CodeBlock code={codeText(children).replace(/\n$/, '')} />}</div>,
          code: ({ children }) => (
            <code className="border border-paper-line-soft bg-paper-raised px-1 py-0.5 font-mono text-[0.85em] text-ink">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-2 border-paper-line text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-2 border-paper-line-soft bg-paper-raised px-2 py-1.5 font-body font-bold uppercase tracking-wide text-ink">
              {children}
            </th>
          ),
          td: ({ children }) => <td className="border-2 border-paper-line-soft px-2 py-1.5 text-ink">{children}</td>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
