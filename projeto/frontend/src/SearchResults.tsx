import { TOTAL_CAP, type Falha } from './api'
import { formatInteger } from './format'
import { temFiltros, textoParcial, tituloResultados, tituloVazio, totalLimitado } from './mensagens'
import { ResultsList } from './ResultsList'
import { ResultsTable } from './ResultsTable'
import type { Busca, Meta, Servidor } from './types'
import type { SearchState } from './useBuscaServidores'

/** Área abaixo do formulário: um componente por estado da busca (docs/design/estados.html). */
export function SearchResults({ state }: { state: SearchState }) {
  switch (state.kind) {
    case 'loading':
      return <Esqueleto />
    case 'empty':
      return <EstadoVazio busca={state.busca} />
    case 'error':
      return <AvisoFalha falha={state.falha} />
    case 'ok':
      return <Resultados busca={state.busca} servidores={state.servidores} meta={state.meta} />
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

function Resultados({ busca, servidores, meta }: { busca: Busca; servidores: Servidor[]; meta: Meta }) {
  const parcial = textoParcial(servidores.length, meta)
  const similar = busca.modo === 'similar'
  return (
    <section className="resultados" aria-labelledby="res-titulo">
      <div className="resultados__topo">
        <div>
          <h2 className="titulo-secao" id="res-titulo">
            {tituloResultados(busca, meta)}
          </h2>
          {parcial !== null && <p className="aux">{parcial}</p>}
        </div>
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

      <ResultsTable servidores={servidores} similar={similar} />
      <ResultsList servidores={servidores} similar={similar} />
    </section>
  )
}
