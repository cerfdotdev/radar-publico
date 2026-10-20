import type { MouseEvent } from 'react'
import { formatInteger } from './format'
import type { Busca, Meta } from './types'
import { hrefDaBusca, PAGINA_MIN } from './useBuscaServidores'

/** Até esse total, mostra todas as páginas; acima, a primeira, a última e as vizinhas da atual. */
const MAX_PAGINAS_SEM_RETICENCIAS = 7

interface PaginacaoProps {
  busca: Busca
  meta: Meta
  /** Itens desta página (a última pode ter menos que per_page). */
  quantidade: number
  onNavegar: (busca: Busca) => void
}

function paginasVisiveis(atual: number, total: number): (number | null)[] {
  if (total <= MAX_PAGINAS_SEM_RETICENCIAS) return Array.from({ length: total }, (_, indice) => indice + PAGINA_MIN)
  const paginas = [...new Set([PAGINA_MIN, atual - 1, atual, atual + 1, total])]
    .filter((pagina) => pagina >= PAGINA_MIN && pagina <= total)
    .sort((a, b) => a - b)
  const resultado: (number | null)[] = []
  for (const pagina of paginas) {
    const anterior = resultado[resultado.length - 1]
    if (typeof anterior === 'number' && pagina - anterior > 1) resultado.push(null)
    resultado.push(pagina)
  }
  return resultado
}

/** Páginas da busca (docs/design/busca.html): números no desktop, Anterior/Próxima no celular. */
export function Paginacao({ busca, meta, quantidade, onNavegar }: PaginacaoProps) {
  if (meta.total_pages <= PAGINA_MIN) return null
  const inicio = (meta.page - 1) * meta.per_page + 1
  const fim = inicio + quantidade - 1
  const semAnterior = meta.page <= PAGINA_MIN
  const semProxima = meta.page >= meta.total_pages
  // Desativados, anterior e próxima apontam para a própria página, nunca para uma que não existe.
  const anterior = semAnterior ? meta.page : meta.page - 1
  const proxima = semProxima ? meta.page : meta.page + 1

  // Links de verdade (abrem em outra aba); o clique comum troca a página sem recarregar.
  const href = (pagina: number) => hrefDaBusca({ ...busca, pagina })
  const aoClicar = (pagina: number) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    if (pagina >= PAGINA_MIN && pagina <= meta.total_pages && pagina !== meta.page) onNavegar({ ...busca, pagina })
  }

  return (
    <nav className="paginacao" aria-label="Paginação">
      <span className="aux">
        Mostrando {formatInteger(inicio)}–{formatInteger(fim)} de {formatInteger(meta.total)} · página{' '}
        {formatInteger(meta.page)} de {formatInteger(meta.total_pages)}
      </span>
      <div className="paginacao__paginas">
        <a
          href={href(anterior)}
          aria-label="Página anterior"
          aria-disabled={semAnterior}
          tabIndex={semAnterior ? -1 : undefined}
          onClick={aoClicar(anterior)}
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
              href={href(pagina)}
              aria-current={pagina === meta.page ? 'page' : undefined}
              onClick={aoClicar(pagina)}
            >
              {formatInteger(pagina)}
            </a>
          ),
        )}
        <a
          href={href(proxima)}
          aria-label="Próxima página"
          aria-disabled={semProxima}
          tabIndex={semProxima ? -1 : undefined}
          onClick={aoClicar(proxima)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </a>
      </div>
      {/* Celular: só anterior, posição e próxima (o CSS mostra um ou outro bloco). */}
      <div className="paginacao__celular">
        <a
          href={href(anterior)}
          aria-disabled={semAnterior}
          tabIndex={semAnterior ? -1 : undefined}
          onClick={aoClicar(anterior)}
        >
          Anterior
        </a>
        <span className="aux">
          {formatInteger(meta.page)} de {formatInteger(meta.total_pages)}
        </span>
        <a
          href={href(proxima)}
          aria-disabled={semProxima}
          tabIndex={semProxima ? -1 : undefined}
          onClick={aoClicar(proxima)}
        >
          Próxima
        </a>
      </div>
    </nav>
  )
}
