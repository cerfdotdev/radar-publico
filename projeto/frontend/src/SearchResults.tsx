import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react'
import { TOTAL_CAP, type Falha } from './api'
import { DetalheServidor } from './DetalheServidor'
import { LIMITE_PADRAO, padraoParecido } from './filtros'
import { formatInteger } from './format'
import { temFiltros, tituloPaginaInexistente, tituloResultados, tituloVazio, totalLimitado } from './mensagens'
import { Paginacao } from './Paginacao'
import { ResultsList } from './ResultsList'
import { ResultsTable } from './ResultsTable'
import type { Busca, Meta, Servidor } from './types'
import { hrefDaBusca, PAGINA_PADRAO, POR_PAGINA_OPCOES, type SearchState } from './useBuscaServidores'

interface SearchResultsProps {
  state: SearchState
  /**
   * Ação vinda da própria área de resultados (página, itens por página, tentar de novo):
   * o elemento clicado some durante o carregamento, então o foco vai para o título do
   * que aparecer em seguida (`focarTitulo`).
   */
  onNavegar: (busca: Busca) => void
  focarTitulo: boolean
}

/** Área abaixo do formulário: um componente por estado da busca (docs/design/estados.html). */
export function SearchResults({ state, onNavegar, focarTitulo }: SearchResultsProps) {
  switch (state.kind) {
    case 'loading':
      return <Esqueleto />
    case 'empty':
      return <EstadoVazio busca={state.busca} focarTitulo={focarTitulo} onNavegar={onNavegar} />
    case 'no-page':
      return (
        <PaginaInexistente
          busca={state.busca}
          ultimaPagina={state.ultimaPagina}
          focarTitulo={focarTitulo}
          onNavegar={onNavegar}
        />
      )
    case 'error':
      return <AvisoFalha falha={state.falha} onTentarDeNovo={() => onNavegar({ ...state.busca })} />
    case 'ok':
      return (
        <Resultados
          busca={state.busca}
          servidores={state.servidores}
          meta={state.meta}
          focarTitulo={focarTitulo}
          onNavegar={onNavegar}
        />
      )
    default:
      // Ocioso, ou erro de validação, que aparece no próprio campo.
      return null
  }
}

/** Título que recebe o foco ao aparecer, quando a busca veio de um clique nos resultados. */
function useFocoNoTitulo(focar: boolean) {
  const ref = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (focar) ref.current?.focus()
  }, [focar])
  return ref
}

/** Link para outra busca que abre igual em outra aba; o clique comum busca sem recarregar. */
function LinkDeBusca({
  busca,
  onNavegar,
  className,
  children,
}: {
  busca: Busca
  onNavegar: (busca: Busca) => void
  className: string
  children: ReactNode
}) {
  return (
    <a
      className={className}
      href={hrefDaBusca(busca)}
      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
        event.preventDefault()
        onNavegar(busca)
      }}
    >
      {children}
    </a>
  )
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

interface EstadoProps {
  busca: Busca
  focarTitulo: boolean
  onNavegar: (busca: Busca) => void
}

function EstadoVazio({ busca, focarTitulo, onNavegar }: EstadoProps) {
  const tituloRef = useFocoNoTitulo(focarTitulo)
  // Nome exato sem filtros: oferece a busca parecida já montada (docs/design/estados.html).
  const padrao = busca.modo === 'exato' && !temFiltros(busca) ? padraoParecido(busca.termo) : null
  return (
    <section className="estado-vazio" aria-labelledby="vazio-titulo">
      <h2 className="subtitulo" id="vazio-titulo" ref={tituloRef} tabIndex={-1}>
        {tituloVazio(busca)}
      </h2>
      <p>{explicacaoVazio(busca)}</p>
      {padrao !== null && (
        <LinkDeBusca
          className="btn btn--secundario"
          busca={{ ...busca, modo: 'similar', termo: padrao, limite: LIMITE_PADRAO, pagina: PAGINA_PADRAO }}
          onNavegar={onNavegar}
        >
          {/* Um só bloco de texto: no celular, quebra como frase, não em colunas do flex. */}
          <span>
            Buscar nomes parecidos: <span className="mono">{padrao}</span>
          </span>
        </LinkDeBusca>
      )}
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

/** 404 PAGINA_INEXISTENTE: link antigo ou página digitada na URL; leva à última página válida. */
function PaginaInexistente({ busca, ultimaPagina, focarTitulo, onNavegar }: EstadoProps & { ultimaPagina: number | null }) {
  const tituloRef = useFocoNoTitulo(focarTitulo)
  const destino = ultimaPagina ?? PAGINA_PADRAO
  const paginas = ultimaPagina === 1 ? '1 página' : `${formatInteger(destino)} páginas`
  return (
    <section className="estado-vazio" aria-labelledby="pagina-titulo">
      <h2 className="subtitulo" id="pagina-titulo" ref={tituloRef} tabIndex={-1}>
        {tituloPaginaInexistente(busca.pagina)}
      </h2>
      <p>
        {ultimaPagina === null ? '' : `Esta busca tem ${paginas}. `}O link pode ser de uma busca anterior, com outros
        resultados.
      </p>
      <LinkDeBusca className="btn btn--primario" busca={{ ...busca, pagina: destino }} onNavegar={onNavegar}>
        {ultimaPagina === null ? 'Ir para a primeira página' : `Ir para a página ${formatInteger(destino)}`}
      </LinkDeBusca>
    </section>
  )
}

function AvisoFalha({ falha, onTentarDeNovo }: { falha: Falha; onTentarDeNovo: () => void }) {
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
    <div className="falha">
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
      <button className="btn btn--secundario" type="button" onClick={onTentarDeNovo}>
        Tentar de novo
      </button>
    </div>
  )
}

interface ResultadosProps {
  busca: Busca
  servidores: Servidor[]
  meta: Meta
  focarTitulo: boolean
  onNavegar: (busca: Busca) => void
}

function Resultados({ busca, servidores, meta, focarTitulo, onNavegar }: ResultadosProps) {
  const tituloRef = useFocoNoTitulo(focarTitulo)
  const similar = busca.modo === 'similar'
  const unico = meta.total === 1 && servidores.length === 1
  // A busca parecida vem inteira, até o limite, sem páginas; o resultado único vira o detalhe.
  const paginada = !similar && !unico
  const opcoesPorPagina: number[] = [...POR_PAGINA_OPCOES]
  if (!opcoesPorPagina.includes(meta.per_page)) opcoesPorPagina.push(meta.per_page)

  return (
    <section className="resultados" aria-labelledby="res-titulo">
      <div className="resultados__topo">
        <div>
          <h2 className="titulo-secao" id="res-titulo" ref={tituloRef} tabIndex={-1}>
            {tituloResultados(busca, meta)}
          </h2>
        </div>
        {paginada && (
          <label className="por-pagina">
            Por página
            <select
              value={meta.per_page}
              onChange={(event) =>
                onNavegar({ ...busca, pagina: PAGINA_PADRAO, porPagina: Number(event.target.value) })
              }
              aria-label="Resultados por página"
            >
              {opcoesPorPagina.map((quantidade) => (
                <option key={quantidade} value={quantidade}>
                  {quantidade}
                </option>
              ))}
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
              A contagem para em {formatInteger(TOTAL_CAP)} resultados e só eles têm páginas. Acrescente o nome completo
              ou outro filtro para chegar a quem você procura.
            </span>
          </div>
        </div>
      )}

      {unico ? (
        <DetalheServidor key={servidores[0].id} resumo={servidores[0]} />
      ) : (
        <>
          <ResultsTable servidores={servidores} similar={similar} />
          <ResultsList servidores={servidores} similar={similar} />
          {paginada && <Paginacao busca={busca} meta={meta} quantidade={servidores.length} onNavegar={onNavegar} />}
        </>
      )}
    </section>
  )
}
