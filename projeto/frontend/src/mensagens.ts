// Textos da área de resultados, compartilhados entre a tela e a região viva.
import { TOTAL_CAP } from './api'
import { formatInteger } from './format'
import type { Meta } from './types'
import type { SearchState } from './useBuscaServidores'

/** A contagem parou no limite da API: o total real é maior que meta.total. */
export function totalLimitado(meta: Meta): boolean {
  return meta.total_exato === false
}

export function tituloResultados(termo: string, meta: Meta): string {
  if (totalLimitado(meta)) {
    return `Mais de ${formatInteger(TOTAL_CAP)} resultados para “${termo}”`
  }
  const rotulo = meta.total === 1 ? 'resultado encontrado' : 'resultados encontrados'
  return `${formatInteger(meta.total)} ${rotulo} para “${termo}”`
}

/** Quando a página não traz todos os resultados (a paginação é da issue #21). */
export function textoParcial(quantidade: number, meta: Meta): string | null {
  if (meta.total <= quantidade) return null
  return quantidade === 1
    ? 'Mostrando só o primeiro.'
    : `Mostrando os ${formatInteger(quantidade)} primeiros.`
}

export function tituloVazio(termo: string): string {
  return `Nenhum vínculo com o nome “${termo}”`
}

/**
 * Texto da região viva da página. Erros de campo e falhas em tom de erro já são
 * anunciados pelos próprios avisos (role="alert"), então ficam de fora.
 */
export function anunciar(state: SearchState): string {
  switch (state.kind) {
    case 'loading':
      return 'Buscando…'
    case 'ok': {
      const parcial = textoParcial(state.servidores.length, state.meta)
      const titulo = `${tituloResultados(state.termo, state.meta)}.`
      return parcial === null ? titulo : `${titulo} ${parcial}`
    }
    case 'empty':
      return `${tituloVazio(state.termo)}.`
    case 'error':
      return state.falha.tom === 'info' ? `${state.falha.titulo}. ${state.falha.texto}` : ''
    default:
      return ''
  }
}
