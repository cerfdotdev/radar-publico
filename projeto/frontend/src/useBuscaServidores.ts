import { useCallback, useEffect, useState } from 'react'
import {
  buscarServidores,
  FALHA_INESPERADA,
  type Falha,
  type ParametrosBusca,
  type SearchOutcome,
} from './api'
import { LIMITE_PADRAO, limparTermo, validarBusca, type CampoBusca } from './filtros'
import type { Busca, Meta, ModoBusca, Servidor } from './types'

/** Parâmetros da URL com a busca: recarregar, copiar o link e voltar mantêm os filtros. */
export const NOME_PARAM = 'nome'
export const SIMILAR_PARAM = 'similar'
export const LIMITE_PARAM = 'limit'
export const CARGO_PARAM = 'cargo'
export const ORGAO_PARAM = 'orgao'
export const UF_PARAM = 'uf'
export const PAGE_PARAM = 'page'
export const PER_PAGE_PARAM = 'per_page'

export const PAGINA_PADRAO = 1
export const POR_PAGINA_PADRAO = 20

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
  | { kind: 'loading'; termo: string; modo: ModoBusca }
  | { kind: 'invalid'; termo: string; modo: ModoBusca; message: string; campo: CampoBusca }
  | { kind: 'empty'; termo: string; modo: ModoBusca }
  | { kind: 'ok'; termo: string; modo: ModoBusca; servidores: Servidor[]; meta: Meta }
  | { kind: 'error'; termo: string; modo: ModoBusca; falha: Falha }

interface Resposta {
  busca: Busca
  resultado: SearchOutcome
}

function lerLimite(valor: string | null): number {
  if (valor === null) return LIMITE_PADRAO
  return /^\d+$/.test(valor) ? Number(valor) : Number.NaN
}

function lerInteiro(valor: string | null, padrao: number, minimo: number, maximo: number): number {
  if (valor === null) return padrao
  if (!/^\d+$/.test(valor)) return padrao
  const numero = Number(valor)
  return numero >= minimo && numero <= maximo ? numero : padrao
}

function lerBuscaDaUrl(): Busca | null {
  const params = new URLSearchParams(window.location.search)
  const modo: ModoBusca = params.has(SIMILAR_PARAM) ? 'similar' : 'exato'
  const busca: Busca = {
    modo,
    termo: limparTermo(params.get(modo === 'similar' ? SIMILAR_PARAM : NOME_PARAM) ?? ''),
    limite: lerLimite(params.get(LIMITE_PARAM)),
    cargo: limparTermo(params.get(CARGO_PARAM) ?? ''),
    orgao: limparTermo(params.get(ORGAO_PARAM) ?? ''),
    uf: (params.get(UF_PARAM) ?? '').trim().toUpperCase(),
    pagina: lerInteiro(params.get(PAGE_PARAM), PAGINA_PADRAO, 1, 10_000),
    porPagina: lerInteiro(params.get(PER_PAGE_PARAM), POR_PAGINA_PADRAO, 1, 100),
  }
  const vazia =
    busca.termo === '' && busca.cargo === '' && busca.orgao === '' && busca.uf === '' && busca.limite === LIMITE_PADRAO
  return vazia ? null : busca
}

function estadoAtual(busca: Busca | null, resposta: Resposta | null): SearchState {
  if (busca === null) return { kind: 'idle' }
  const erro = validarBusca(busca)
  if (erro !== null) {
    return { kind: 'invalid', termo: busca.termo, modo: busca.modo, message: erro.mensagem, campo: erro.campo }
  }
  if (resposta?.busca !== busca) return { kind: 'loading', termo: busca.termo, modo: busca.modo }

  const resultado = resposta.resultado
  switch (resultado.kind) {
    case 'invalid':
      return { kind: 'invalid', termo: busca.termo, modo: busca.modo, message: resultado.message, campo: 'termo' }
    case 'ok':
      return { kind: 'ok', termo: busca.termo, modo: busca.modo, servidores: resultado.servidores, meta: resultado.meta }
    case 'empty':
      return { kind: 'empty', termo: busca.termo, modo: busca.modo }
    case 'error':
      return { kind: 'error', termo: busca.termo, modo: busca.modo, falha: resultado.falha }
  }
}

function parametrosDaBusca(busca: Busca): ParametrosBusca {
  const parametros: ParametrosBusca = {}
  if (busca.termo !== '') {
    if (busca.modo === 'similar') {
      parametros.similar = busca.termo
      parametros.limit = busca.limite
    } else {
      parametros.nome = busca.termo
    }
  }
  if (busca.cargo !== '') parametros.cargo = busca.cargo
  if (busca.orgao !== '') parametros.orgao = busca.orgao
  if (busca.uf !== '') parametros.uf = busca.uf
  if (busca.modo !== 'similar') {
    if (busca.pagina !== PAGINA_PADRAO) parametros.page = busca.pagina
    if (busca.porPagina !== POR_PAGINA_PADRAO) parametros.per_page = busca.porPagina
  }
  return parametros
}

function queryDaUrl(busca: Busca): URLSearchParams {
  const parametros = parametrosDaBusca(busca)
  const query = new URLSearchParams()
  if (parametros.nome !== undefined) query.set(NOME_PARAM, parametros.nome)
  if (parametros.similar !== undefined) query.set(SIMILAR_PARAM, parametros.similar)
  if (parametros.limit !== undefined) query.set(LIMITE_PARAM, String(parametros.limit))
  if (parametros.cargo !== undefined) query.set(CARGO_PARAM, parametros.cargo)
  if (parametros.orgao !== undefined) query.set(ORGAO_PARAM, parametros.orgao)
  if (parametros.uf !== undefined) query.set(UF_PARAM, parametros.uf)
  if (parametros.page !== undefined) query.set(PAGE_PARAM, String(parametros.page))
  if (parametros.per_page !== undefined) query.set(PER_PAGE_PARAM, String(parametros.per_page))
  return query
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
    const url = new URL(window.location.href)
    for (const parametro of PARAMETROS) url.searchParams.delete(parametro)
    for (const [parametro, valor] of queryDaUrl(novaBusca)) {
      url.searchParams.set(parametro, valor)
    }
    if (url.searchParams.toString() === '') url.search = ''

    // Repetir a busca atual não empilha outra entrada igual no histórico.
    if (url.search === window.location.search) {
      window.history.replaceState(null, '', url)
    } else {
      window.history.pushState(null, '', url)
    }
    setBusca(novaBusca)
  }, [])

  return { busca: busca ?? BUSCA_VAZIA, termo: busca?.termo ?? '', state: estadoAtual(busca, resposta), buscar }
}
