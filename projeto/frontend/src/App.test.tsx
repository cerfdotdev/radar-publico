import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App Component', () => {
  it('renders the header and brand title', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: /radar público/i })).toBeInTheDocument()
  })

  it('renders the API test button', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /testar conexão com \/api\/health/i })).toBeInTheDocument()
  })
})
