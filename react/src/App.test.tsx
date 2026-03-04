import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toBeDefined()
  })

  it('renders Demetra text', () => {
    render(<App />)
    expect(screen.getByText('Demetra')).toBeDefined()
  })
})
