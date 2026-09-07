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
    expect(screen.getByRole('heading', { name: /how it works/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /everything you need to trust a deploy/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /start where you are/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/PulithThewmika/kubex',
    )
    expect(screen.getByRole('link', { name: 'Docs' })).toHaveAttribute('href')
  })
})
