import { useCallback, useEffect, useState } from 'react'
import { buscarServidores, FALHA_INESPERADA, TOTAL_CAP, type ParametrosBusca, type SearchOutcome } from './api'
import { aceitaFiltros, LIMITE_PADRAO, validarBusca } from './filtros'
import { limparNome } from './nome'
import type { Busca, ModoBusca } from './types'

/** Parâmetros da URL com a busca: recarregar, copiar o link e voltar mantêm os filtros. */
export const NOME_PARAM = 'nome'
export const SIMILAR_PARAM = 'similar'
export const LIMITE_PARAM = 'limit'
export const CARGO_PARAM = 'cargo'
export const ORGAO_PARAM = 'orgao'
export const UF_PARAM = 'uf'
export const PAGE_PARAM = 'page'
export const PER_PAGE_PARAM = 'per_page'

/** `page` e `per_page` de docs/api.md. Só existem páginas até o 10.000º resultado. */
export const PAGINA_MIN = 1
export const PAGINA_PADRAO = PAGINA_MIN
export const PAGINA_MAX = TOTAL_CAP
export const POR_PAGINA_MIN = 1
export const POR_PAGINA_MAX = 100
export const POR_PAGINA_PADRAO = 20
/** Opções do seletor "Por página" (docs/design/busca.html). */
export const POR_PAGINA_OPCOES = [20, 50, 100] as const

const PARAMETROS = [
  NOME_PARAM,
  SIMILAR_PARAM,
  LIMITE_PARAM,
  CARGO_PARAM,
  ORGAO_PARAM,
  UF_PARAM,
  PAGE_PARAM,
  PER_PAGE_PARAM,
] as const

export const BUSCA_VAZIA: Busca = {
  modo: 'exato',
  termo: '',
  limite: LIMITE_PADRAO,
  cargo: '',
  orgao: '',
  uf: '',
  pagina: PAGINA_PADRAO,
  porPagina: POR_PAGINA_PADRAO,
}

export type SearchState =
  | { kind: 'idle' }
  | { kind: 'loading'; busca: Busca }
  | (SearchOutcome & { busca: Busca })

// Cada busca é um objeto novo: repetir a mesma busca também refaz a requisição,
// e a resposta só vale para o objeto que a pediu.
interface Resposta {
  busca: Busca
  resultado: SearchOutcome
}

function lerLimite(valor: string | null): number {
  if (valor === null) return LIMITE_PADRAO
  return /^\d+$/.test(valor.trim()) ? Number(valor) : Number.NaN
}

/** Página e itens por página da URL; fora da faixa da API, vale o padrão (link velho ou digitado). */
function lerInteiro(valor: string | null, padrao: number, minimo: number, maximo: number): number {
  if (valor === null || !/^\d+$/.test(valor.trim())) return padrao
  const numero = Number(valor)
  return numero >= minimo && numero <= maximo ? numero : padrao
}

function lerBuscaDaUrl(): Busca | null {
  const params = new URLSearchParams(window.location.search)
  const ler = (parametro: string) => limparNome(params.get(parametro) ?? '')
  const modo: ModoBusca = params.has(SIMILAR_PARAM) ? 'similar' : 'exato'
  const busca: Busca = {
    modo,
    termo: ler(modo === 'similar' ? SIMILAR_PARAM : NOME_PARAM),
    limite: lerLimite(params.get(LIMITE_PARAM)),
    cargo: ler(CARGO_PARAM),
    orgao: ler(ORGAO_PARAM),
    uf: ler(UF_PARAM).toUpperCase(),
    pagina: lerInteiro(params.get(PAGE_PARAM), PAGINA_PADRAO, PAGINA_MIN, PAGINA_MAX),
    porPagina: lerInteiro(params.get(PER_PAGE_PARAM), POR_PAGINA_PADRAO, POR_PAGINA_MIN, POR_PAGINA_MAX),
  }
  const vazia =
    busca.termo === '' && busca.cargo === '' && busca.orgao === '' && busca.uf === '' && busca.limite === LIMITE_PADRAO
  return vazia ? null : busca
}

/**
 * O que vai para a API e para a URL: só os filtros preenchidos que o modo aceita.
 * A busca parecida também não pagina: a API devolve tudo de uma vez, até o limite.
 */
function parametrosDaBusca(busca: Busca): ParametrosBusca {
  if (!aceitaFiltros(busca.modo)) return { similar: busca.termo, limit: busca.limite }
  const parametros: ParametrosBusca = {}
  if (busca.termo !== '') parametros.nome = busca.termo
  if (busca.cargo !== '') parametros.cargo = busca.cargo
  if (busca.orgao !== '') parametros.orgao = busca.orgao
  if (busca.uf !== '') parametros.uf = busca.uf
  if (busca.pagina !== PAGINA_PADRAO) parametros.page = busca.pagina
  if (busca.porPagina !== POR_PAGINA_PADRAO) parametros.per_page = busca.porPagina
  return parametros
}

function montarUrl(busca: Busca): URL {
  const url = new URL(window.location.href)
  for (const parametro of PARAMETROS) url.searchParams.delete(parametro)
  for (const [parametro, valor] of Object.entries(parametrosDaBusca(busca))) {
    url.searchParams.set(parametro, String(valor))
  }
  if (url.searchParams.toString() === '') url.search = ''
  return url
}

/** Link da busca (paginação, "ir para a página"): abre igual em outra aba. */
export function hrefDaBusca(busca: Busca): string {
  const url = montarUrl(busca)
  return `${url.pathname}${url.search}`
}

function estadoAtual(busca: Busca | null, resposta: Resposta | null): SearchState {
  if (busca === null) return { kind: 'idle' }
  const erro = validarBusca(busca)
  if (erro !== null) return { kind: 'invalid', busca, campo: erro.campo, message: erro.mensagem }
  if (resposta?.busca !== busca) return { kind: 'loading', busca }
  return { ...resposta.resultado, busca }
}

/** Busca por nome exato ou parecido com filtros combinados, guardada na URL. */
export function useBuscaServidores() {
  const [busca, setBusca] = useState(lerBuscaDaUrl)
  const [resposta, setResposta] = useState<Resposta | null>(null)

  // Voltar e avançar no navegador: a URL é a fonte da verdade da busca.
  useEffect(() => {
    const aoNavegar = () => setBusca(lerBuscaDaUrl())
    window.addEventListener('popstate', aoNavegar)
    return () => window.removeEventListener('popstate', aoNavegar)
  }, [])

  // Uma requisição por busca. Trocar de busca ou desmontar a tela cancela a anterior,
  // e uma resposta cancelada nunca sobrescreve a atual (nem no StrictMode, que monta
  // o efeito duas vezes em desenvolvimento).
  useEffect(() => {
    if (busca === null || validarBusca(busca) !== null) return
    const controller = new AbortController()
    buscarServidores(parametrosDaBusca(busca), controller.signal).then(
      (resultado) => {
        if (!controller.signal.aborted) setResposta({ busca, resultado })
      },
      () => {
        // buscarServidores só rejeita quando cancelada; outro motivo não pode travar a tela.
        if (!controller.signal.aborted) {
          setResposta({ busca, resultado: { kind: 'error', falha: FALHA_INESPERADA } })
        }
      },
    )
    return () => controller.abort()
  }, [busca])

  const buscar = useCallback((novaBusca: Busca) => {
    const url = montarUrl(novaBusca)
    // Repetir a busca atual não empilha outra entrada igual no histórico.
    if (url.search === window.location.search) {
      window.history.replaceState(null, '', url)
    } else {
      window.history.pushState(null, '', url)
    }
    setBusca(novaBusca)
  }, [])

  return { busca: busca ?? BUSCA_VAZIA, state: estadoAtual(busca, resposta), buscar }
}
