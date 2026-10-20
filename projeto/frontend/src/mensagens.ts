// Textos da área de resultados, compartilhados entre a tela e a região viva.
import { TOTAL_CAP } from './api'
import { formatInteger } from './format'
import type { Busca, Meta } from './types'
import type { SearchState } from './useBuscaServidores'

/** A contagem parou no limite da API: o total real é maior que meta.total. */
export function totalLimitado(meta: Meta): boolean {
  return meta.total_exato === false
}

/** Só filtros além do nome (cargo, órgão ou UF). */
export function temFiltros(busca: Busca): boolean {
  return busca.cargo !== '' || busca.orgao !== '' || busca.uf !== ''
}

/** O que foi buscado, para os títulos: ' para “Maria”, cargo “professor” em RJ'. */
export function descreverBusca(busca: Busca): string {
  const partes = [
    busca.termo === '' ? null : `“${busca.termo}”`,
    busca.cargo === '' ? null : `cargo “${busca.cargo}”`,
    busca.orgao === '' ? null : `órgão “${busca.orgao}”`,
  ].filter((parte) => parte !== null)
  const para = partes.length === 0 ? '' : ` para ${partes.join(', ')}`
  return busca.uf === '' ? para : `${para} em ${busca.uf}`
}

export function tituloResultados(busca: Busca, meta: Meta): string {
  if (busca.modo === 'similar') {
    // A API devolve os mais parecidos primeiro, até o limite pedido, sem paginar.
    return meta.total === 1
      ? `1 nome parecido com “${busca.termo}”`
      : `Os ${formatInteger(meta.total)} nomes mais parecidos com “${busca.termo}”`
  }
  if (totalLimitado(meta)) {
    return `Mais de ${formatInteger(TOTAL_CAP)} resultados${descreverBusca(busca)}`
  }
  const rotulo = meta.total === 1 ? 'resultado encontrado' : 'resultados encontrados'
  return `${formatInteger(meta.total)} ${rotulo}${descreverBusca(busca)}`
}

/** Quando a página não traz todos os resultados (a paginação é da issue #21). */
export function textoParcial(quantidade: number, meta: Meta): string | null {
  if (meta.total <= quantidade) return null
  return quantidade === 1
    ? 'Mostrando só o primeiro.'
    : `Mostrando os ${formatInteger(quantidade)} primeiros.`
}

export function tituloVazio(busca: Busca): string {
  if (busca.modo === 'similar') return `Nenhum nome parecido com “${busca.termo}”`
  if (!temFiltros(busca)) return `Nenhum vínculo com o nome “${busca.termo}”`
  return `Nenhum vínculo encontrado${descreverBusca(busca)}`
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
      const titulo = `${tituloResultados(state.busca, state.meta)}.`
      return parcial === null ? titulo : `${titulo} ${parcial}`
    }
    case 'empty':
      return `${tituloVazio(state.busca)}.`
    case 'error':
      return state.falha.tom === 'info' ? `${state.falha.titulo}. ${state.falha.texto}` : ''
    default:
      return ''
  }
}
