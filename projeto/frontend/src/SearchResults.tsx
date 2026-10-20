import { TOTAL_CAP, type Falha } from './api'
import type { MouseEvent } from 'react'
import { DetalheServidor } from './DetalheServidor'
import { formatInteger } from './format'
import { temFiltros, textoParcial, tituloResultados, tituloVazio, totalLimitado } from './mensagens'
import { ResultsList } from './ResultsList'
import { ResultsTable } from './ResultsTable'
import type { Busca, Meta, Servidor } from './types'
import { PAGE_PARAM, type SearchState } from './useBuscaServidores'

interface SearchResultsProps {
  state: SearchState
  onPagina?: (pagina: number) => void
  onPorPagina?: (porPagina: number) => void
}

/** Área abaixo do formulário: um componente por estado da busca (docs/design/estados.html). */
export function SearchResults({
  state,
  onPagina = () => undefined,
  onPorPagina = () => undefined,
}: SearchResultsProps) {
  switch (state.kind) {
    case 'loading':
      return <Esqueleto />
    case 'empty':
      return <EstadoVazio busca={state.busca} />
    case 'error':
      return <AvisoFalha falha={state.falha} />
    case 'ok':
      return (
        <Resultados
          busca={state.busca}
          servidores={state.servidores}
          meta={state.meta}
          onPagina={onPagina}
          onPorPagina={onPorPagina}
        />
      )
    default:
      // Ocioso, ou erro de validação, que aparece no próprio campo.
      return null
  }
}

function Esqueleto() {
  // Só visual: a região viva da página anuncia "Buscando…".
  return (
    <div className="esqueleto" aria-hidden="true">
      <div className="esqueleto__topo" />
      <div className="esqueleto__linha">
        <i />
        <i />
        <i />
      </div>
      <div className="esqueleto__linha">
        <i />
        <i />
        <i />
      </div>
      <div className="esqueleto__linha">
        <i />
        <i />
        <i />
      </div>
    </div>
  )
}

function EstadoVazio({ busca }: { busca: Busca }) {
  return (
    <section className="estado-vazio" aria-labelledby="vazio-titulo">
      <h2 className="subtitulo" id="vazio-titulo">
        {tituloVazio(busca)}
      </h2>
      <p>{explicacaoVazio(busca)}</p>
    </section>
  )
}

function explicacaoVazio(busca: Busca): string {
  if (busca.modo === 'similar') {
    return 'O padrão vale para o nome inteiro: use % no lugar das partes que você não sabe, como em %MARIA%SILVA%, ou confira a grafia.'
  }
  if (temFiltros(busca)) {
    return 'Nenhum vínculo atende a todos os filtros ao mesmo tempo. Tire um filtro ou confira a grafia.'
  }
  return 'A busca por nome exato só encontra o nome completo, escrito como no registro. Nomes do meio abreviados ou trocados não aparecem.'
}

function AvisoFalha({ falha }: { falha: Falha }) {
  if (falha.tom === 'info') {
    // Limite de uso: tom informativo, anunciado pela região viva da página.
    return (
      <div className="aviso aviso--info">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
        <div>
          <strong>{falha.titulo}</strong>
          <span>{falha.texto}</span>
        </div>
      </div>
    )
  }
  return (
    <div className="aviso aviso--erro" role="alert">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div>
        <strong>{falha.titulo}</strong>
        <span>{falha.texto}</span>
      </div>
    </div>
  )
}

interface ResultadosProps {
  busca: Busca
  servidores: Servidor[]
  meta: Meta
  onPagina: (pagina: number) => void
  onPorPagina: (porPagina: number) => void
}

function Resultados({ busca, servidores, meta, onPagina, onPorPagina }: ResultadosProps) {
  const parcial = textoParcial(servidores.length, meta)
  const similar = busca.modo === 'similar'
  const unico = meta.total === 1 && servidores.length === 1

  return (
    <section className="resultados" aria-labelledby="res-titulo">
      <div className="resultados__topo">
        <div>
          <h2 className="titulo-secao" id="res-titulo">
            {tituloResultados(busca, meta)}
          </h2>
          {parcial !== null && <p className="aux">{parcial}</p>}
        </div>
        {!unico && (
          <label className="por-pagina">
            Por página
            <select
              value={meta.per_page}
              onChange={(event) => onPorPagina(Number(event.target.value))}
              aria-label="Resultados por página"
            >
              {[20, 50, 100].map((quantidade) => (
                <option key={quantidade} value={quantidade}>
                  {quantidade}
                </option>
              ))}
              {![20, 50, 100].includes(meta.per_page) && (
                <option value={meta.per_page}>{meta.per_page}</option>
              )}
            </select>
          </label>
        )}
      </div>

      {totalLimitado(meta) && (
        <div className="aviso aviso--atencao">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M12 3l9 16H3z" />
            <path d="M12 10v4M12 17h.01" />
          </svg>
          <div>
            <strong>Refine a busca</strong>
            <span>
              A contagem para em {formatInteger(TOTAL_CAP)} resultados. Acrescente o nome completo ou outro filtro
              para chegar a quem você procura.
            </span>
          </div>
        </div>
      )}

      {unico ? (
        <DetalheServidor resumo={servidores[0]} />
      ) : (
        <>
          <ResultsTable servidores={servidores} similar={similar} />
          <ResultsList servidores={servidores} similar={similar} />
          <Paginacao
            meta={meta}
            quantidade={servidores.length}
            onPagina={onPagina}
          />
        </>
      )}
    </section>
  )
}

function paginasVisiveis(atual: number, total: number): (number | null)[] {
  if (total <= 7) return Array.from({ length: total }, (_, indice) => indice + 1)
  const paginas = [...new Set([1, atual - 1, atual, atual + 1, total])]
    .filter((pagina) => pagina >= 1 && pagina <= total)
    .sort((a, b) => a - b)
  const resultado: (number | null)[] = []
  for (const pagina of paginas) {
    const anterior = resultado[resultado.length - 1]
    if (typeof anterior === 'number' && pagina - anterior > 1) resultado.push(null)
    resultado.push(pagina)
  }
  return resultado
}

function Paginacao({
  meta,
  quantidade,
  onPagina,
}: {
  meta: Meta
  quantidade: number
  onPagina: (pagina: number) => void
}) {
  if (meta.total_pages <= 1) return null
  const inicio = (meta.page - 1) * meta.per_page + 1
  const fim = inicio + quantidade - 1

  const hrefPagina = (pagina: number) => {
    const params = new URLSearchParams(window.location.search)
    if (pagina <= 1) params.delete(PAGE_PARAM)
    else params.set(PAGE_PARAM, String(pagina))
    const query = params.toString()
    return `${window.location.pathname}${query === '' ? '' : `?${query}`}`
  }

  const navegar = (event: MouseEvent<HTMLAnchorElement>, pagina: number) => {
    event.preventDefault()
    if (pagina >= 1 && pagina <= meta.total_pages && pagina !== meta.page) onPagina(pagina)
  }

  return (
    <nav className="paginacao" aria-label="Paginação">
      <span className="aux">
        Mostrando {formatInteger(inicio)}–{formatInteger(fim)} de {formatInteger(meta.total)} · página {meta.page} de{' '}
        {meta.total_pages}
      </span>
      <div className="paginacao__paginas">
        <a
          href={hrefPagina(meta.page - 1)}
          aria-label="Página anterior"
          aria-disabled={meta.page <= 1}
          tabIndex={meta.page <= 1 ? -1 : undefined}
          onClick={(event) => navegar(event, meta.page - 1)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </a>
        {paginasVisiveis(meta.page, meta.total_pages).map((pagina, indice) =>
          pagina === null ? (
            <span className="paginacao__reticencias" key={`intervalo-${indice}`} aria-hidden="true">
              …
            </span>
          ) : (
            <a
              key={pagina}
              href={hrefPagina(pagina)}
              aria-current={pagina === meta.page ? 'page' : undefined}
              onClick={(event) => navegar(event, pagina)}
            >
              {pagina}
            </a>
          ),
        )}
        <a
          href={hrefPagina(meta.page + 1)}
          aria-label="Próxima página"
          aria-disabled={meta.page >= meta.total_pages}
          tabIndex={meta.page >= meta.total_pages ? -1 : undefined}
          onClick={(event) => navegar(event, meta.page + 1)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </a>
      </div>
    </nav>
  )
}
