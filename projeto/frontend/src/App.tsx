import { useState } from 'react'
import './App.css'

export function App() {
  const [apiStatus, setApiStatus] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function checkApiHealth() {
    setLoading(true)
    try {
      const response = await fetch('/api/health')
      if (response.ok) {
        const data = await response.json().catch(() => ({ status: 'ok' }))
        setApiStatus(`API Conectada: ${JSON.stringify(data)}`)
      } else {
        setApiStatus(`Erro da API: status ${response.status}`)
      }
    } catch (err) {
      setApiStatus(`Falha de conexão com /api: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
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
            roteadas diretamente para o backend via proxy reverso no Nginx (ou Vite dev server).
          </p>
          <button
            type="button"
            className="btn-primary"
            onClick={checkApiHealth}
            disabled={loading}
          >
            {loading ? 'Verificando…' : 'Testar conexão com /api/health'}
          </button>

          {apiStatus && (
            <div
              className={`api-status-badge ${apiStatus.startsWith('API Conectada') ? 'info' : 'err'}`}
              role="status"
              aria-live="polite"
            >
              {apiStatus}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
