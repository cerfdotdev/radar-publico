import './App.css'
import { anunciar } from './mensagens'
import { SearchForm } from './SearchForm'
import { SearchResults } from './SearchResults'
import { SiteHeader } from './SiteHeader'
import { useBuscaServidores } from './useBuscaServidores'

export function App() {
  const { busca, state, buscar } = useBuscaServidores()

  return (
    <>
      <SiteHeader />

      <main className="container pagina">
        <div>
          <h1 className="titulo-pagina">Buscar servidores federais</h1>
          <p className="lead">
            Consulte vínculos de servidores ativos e aposentados do Poder Executivo Federal, com dados abertos do governo.
          </p>
        </div>

        <SearchForm
          busca={busca}
          ocupado={state.kind === 'loading'}
          erroExterno={state.kind === 'invalid' ? { campo: state.campo, mensagem: state.message } : null}
          onBuscar={buscar}
        />

        {/* Região viva única e sempre presente: anuncia "Buscando…" e o resultado da busca. */}
        <output className="sr-only" aria-live="polite">
          {anunciar(state)}
        </output>

        <SearchResults state={state} />

        {/* Meses de referência dos arquivos carregados no banco (docs/dados.md). */}
        <footer className="nota-fonte">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 11v5M12 8h.01" />
          </svg>
          <span>
            Fonte: Gestão de Pessoas do Executivo Federal, dados.gov.br. Ativos com referência em 08/2026; aposentados,
            05/2026. O conjunto de aposentados não informa a UF, por isso ela aparece como “—”.
          </span>
        </footer>
      </main>
    </>
  )
}

export default App
