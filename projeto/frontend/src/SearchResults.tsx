import { TOTAL_CAP, type Falha } from './api'
import { formatInteger } from './format'
import { textoParcial, tituloResultados, tituloVazio, totalLimitado } from './mensagens'
import { ResultsList } from './ResultsList'
import { ResultsTable } from './ResultsTable'
import type { Meta, ModoBusca, Servidor } from './types'
import type { SearchState } from './useBuscaServidores'

/** Área abaixo do formulário: um componente por estado da busca (docs/design/estados.html). */
export function SearchResults({ state }: { state: SearchState }) {
  switch (state.kind) {
    case 'loading':
      return <Esqueleto />
    case 'empty':
      return <EstadoVazio termo={state.termo} modo={state.modo} />
    case 'error':
      return <AvisoFalha falha={state.falha} />
    case 'ok':
      return <Resultados termo={state.termo} servidores={state.servidores} meta={state.meta} />
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

function EstadoVazio({ termo, modo }: { termo: string; modo: ModoBusca }) {
  return (
    <section className="estado-vazio" aria-labelledby="vazio-titulo">
      <h2 className="subtitulo" id="vazio-titulo">
        {tituloVazio(termo)}
      </h2>
      {modo === 'similar' ? (
        <p>Nenhum nome parecido o bastante com o padrão informado. Tente menos partes ou outros filtros.</p>
      ) : (
        <p>
          A busca por nome exato só encontra o nome completo, escrito como no registro. Nomes do meio abreviados ou
          trocados não aparecem.
        </p>
      )}
    </section>
  )
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

function Resultados({ termo, servidores, meta }: { termo: string; servidores: Servidor[]; meta: Meta }) {
  const parcial = textoParcial(servidores.length, meta)
  return (
    <section className="resultados" aria-labelledby="res-titulo">
      <div className="resultados__topo">
        <div>
          <h2 className="titulo-secao" id="res-titulo">
            {tituloResultados(termo, meta)}
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
              A contagem para em {formatInteger(TOTAL_CAP)} resultados. Confira se digitou o nome completo, como no
              registro.
            </span>
          </div>
        </div>
      )}

      <ResultsTable servidores={servidores} />
      <ResultsList servidores={servidores} />
    </section>
  )
}
