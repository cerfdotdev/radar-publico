import { useState } from 'react'
import './App.css'

export const HEALTH_URL = '/api/health'
/** Tempo máximo esperando a API antes de desistir. */
export const HEALTH_TIMEOUT_MS = 5000
const MS_PER_SECOND = 1000

type ApiStatus =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ok'; text: string }
  | { kind: 'error'; text: string }

function isHealthy(body: unknown): boolean {
  return typeof body === 'object' && body !== null && 'status' in body && body.status === 'ok'
}

async function fetchHealth(signal: AbortSignal): Promise<ApiStatus> {
  let response: Response
  try {
    response = await fetch(HEALTH_URL, { signal, headers: { Accept: 'application/json' } })
  } catch {
    if (signal.aborted) {
      return {
        kind: 'error',
        text: `A API não respondeu em ${HEALTH_TIMEOUT_MS / MS_PER_SECOND} s.`,
      }
    }
    return { kind: 'error', text: 'Não foi possível conectar à API.' }
  }

  if (!response.ok) {
    return { kind: 'error', text: `A API respondeu com erro (HTTP ${response.status}).` }
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    return { kind: 'error', text: 'A API respondeu, mas não em JSON.' }
  }

  return isHealthy(body)
    ? { kind: 'ok', text: 'API conectada.' }
    : { kind: 'error', text: 'Resposta inesperada da API.' }
}

export function App() {
  const [status, setStatus] = useState<ApiStatus>({ kind: 'idle' })
  const loading = status.kind === 'loading'

  async function checkApiHealth() {
    if (loading) return
    setStatus({ kind: 'loading' })
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
    try {
      setStatus(await fetchHealth(controller.signal))
    } finally {
      clearTimeout(timer)
    }
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="brand-title">Radar Público</h1>
        <p className="brand-subtitle">
          Consulta cívica a dados abertos de servidores públicos federais
        </p>
      </header>

      <main className="app-main">
        <section className="status-card" aria-labelledby="status-heading">
          <h2 id="status-heading">Ambiente Frontend Inicializado</h2>
          <p>
            Stack Vite + React + TypeScript configurada. As requisições para <code>/api/*</code> são
            roteadas para o backend pelo proxy reverso do Nginx (ou do servidor de desenvolvimento
            do Vite).
          </p>
          {/* aria-disabled em vez de disabled: o botão continua focável enquanto verifica. */}
          <button
            type="button"
            className="btn-primary"
            onClick={checkApiHealth}
            aria-disabled={loading}
            aria-busy={loading}
          >
            {loading ? 'Verificando…' : 'Testar conexão com /api/health'}
          </button>

          {/* <output> tem papel "status" (região viva): sempre presente, para leitores de tela
              anunciarem a mudança. */}
          <output className={`api-status api-status--${status.kind}`}>
            {status.kind === 'ok' || status.kind === 'error' ? status.text : ''}
          </output>
        </section>
      </main>
    </div>
  )
}

export default App
