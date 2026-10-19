import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import App, { HEALTH_TIMEOUT_MS, HEALTH_URL } from './App'

type FakeResponse = { ok: boolean; status: number; json: () => Promise<unknown> }

function respondWith(response: FakeResponse) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function jsonBody(body: unknown, status = 200): FakeResponse {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) }
}

function clickCheck() {
  fireEvent.click(screen.getByRole('button', { name: /testar conexão com \/api\/health/i }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('App', () => {
  it('renders the brand title, the check button and an empty live region', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: /radar público/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /testar conexão/i })).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('reports success only when the API answers {"status": "ok"}', async () => {
    const fetchMock = respondWith(jsonBody({ status: 'ok' }))
    render(<App />)
    clickCheck()
    expect(await screen.findByText('API conectada.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(HEALTH_URL, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('reports the HTTP status on an error response', async () => {
    respondWith(jsonBody({ error: { code: 'SERVIDOR_INDISPONIVEL' } }, 502))
    render(<App />)
    clickCheck()
    expect(await screen.findByText(/HTTP 502/)).toBeInTheDocument()
  })

  it('treats a 200 that is not JSON as an error', async () => {
    respondWith({ ok: true, status: 200, json: () => Promise.reject(new SyntaxError('html')) })
    render(<App />)
    clickCheck()
    expect(await screen.findByText(/não em JSON/)).toBeInTheDocument()
    expect(screen.queryByText('API conectada.')).not.toBeInTheDocument()
  })

  it('treats an unexpected JSON body as an error', async () => {
    respondWith(jsonBody({ status: 'down' }))
    render(<App />)
    clickCheck()
    expect(await screen.findByText('Resposta inesperada da API.')).toBeInTheDocument()
  })

  it('reports a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<App />)
    clickCheck()
    expect(await screen.findByText('Não foi possível conectar à API.')).toBeInTheDocument()
  })

  it('gives up after the timeout', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
          }),
      ),
    )
    render(<App />)
    clickCheck()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(HEALTH_TIMEOUT_MS)
    })
    expect(screen.getByText(/não respondeu em 5 s/)).toBeInTheDocument()
  })

  it('keeps the button focusable and ignores clicks while checking', () => {
    const fetchMock = vi.fn(() => new Promise(() => {}))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const button = screen.getByRole('button', { name: /testar conexão/i })
    button.focus()
    fireEvent.click(button)

    const busy = screen.getByRole('button', { name: /verificando/i })
    expect(busy).not.toBeDisabled()
    expect(busy).toHaveAttribute('aria-disabled', 'true')
    expect(busy).toHaveAttribute('aria-busy', 'true')
    expect(busy).toHaveFocus()

    fireEvent.click(busy)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
