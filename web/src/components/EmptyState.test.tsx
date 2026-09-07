import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No services" description="Connect a repo to begin" />, {
      wrapper: MemoryRouter,
    })
    expect(screen.getByRole('heading', { name: 'No services' })).toBeInTheDocument()
    expect(screen.getByText('Connect a repo to begin')).toBeInTheDocument()
  })

  it('renders a router link action', () => {
    render(<EmptyState title="x" action={{ label: 'Go to settings', to: '/app/settings' }} />, {
      wrapper: MemoryRouter,
    })
    expect(screen.getByRole('link', { name: 'Go to settings' })).toHaveAttribute(
      'href',
      '/app/settings',
    )
  })

  it('renders a button action and fires onClick', () => {
    const onClick = vi.fn()
    render(<EmptyState title="x" action={{ label: 'Retry', onClick }} />, { wrapper: MemoryRouter })
    screen.getByRole('button', { name: 'Retry' }).click()
    expect(onClick).toHaveBeenCalledOnce()
  })
})
