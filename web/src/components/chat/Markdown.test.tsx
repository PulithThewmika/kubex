import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Markdown } from './Markdown'

describe('Markdown', () => {
  it('renders GPT-style bold/list markdown as real elements, not raw asterisks', () => {
    render(<Markdown>{'**payments** is degraded:\n\n- error rate up\n- p99 up'}</Markdown>)
    expect(screen.getByText('payments').tagName).toBe('STRONG')
    expect(screen.getByText('error rate up').closest('ul')).not.toBeNull()
    expect(screen.queryByText(/\*\*/)).toBeNull()
  })

  it('renders fenced code through CodeBlock with a copy button', () => {
    render(<Markdown>{'```\nkubectl get pods\n```'}</Markdown>)
    expect(screen.getByText('kubectl get pods')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  })

  it('renders GFM tables', () => {
    render(<Markdown>{'| svc | score |\n| --- | --- |\n| orders | 82 |'}</Markdown>)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('orders')).toBeInTheDocument()
  })
})
