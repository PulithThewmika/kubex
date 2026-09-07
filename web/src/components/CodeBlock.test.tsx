import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CodeBlock } from './CodeBlock'

let writeText: ReturnType<typeof vi.fn>

beforeEach(() => {
  writeText = vi.fn().mockResolvedValue(undefined)
  Object.assign(navigator, { clipboard: { writeText } })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CodeBlock', () => {
  it('renders the given code', () => {
    render(<CodeBlock code="helm install kubex-agent ./chart" />)
    expect(screen.getByText('helm install kubex-agent ./chart')).toBeInTheDocument()
  })

  it('copies the code to the clipboard and shows confirmation', async () => {
    render(<CodeBlock code="kubectl apply -f install.yaml" />)

    fireEvent.click(screen.getByRole('button', { name: /copy/i }))

    expect(writeText).toHaveBeenCalledWith('kubectl apply -f install.yaml')
    await waitFor(() => expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument())
  })
})
