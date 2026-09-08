import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Landing } from './Landing'

describe('Landing', () => {
  it('renders the hero CTA and every section heading', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('link', { name: /sign in with github/i }).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: /deployment-aware/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /our integrations/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /pick your/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /how it works/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'GitHub' })[0]).toHaveAttribute(
      'href',
      'https://github.com/PulithThewmika/kubex',
    )
    expect(screen.getByRole('link', { name: 'Docs' })).toHaveAttribute('href')
  })

  it('shows the integration tiles the platform reads from', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    )

    for (const name of ['GitHub Actions', 'ArgoCD', 'Kubernetes', 'Prometheus', 'Grafana', 'Slack']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
  })
})
