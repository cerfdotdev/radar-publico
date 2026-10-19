// Apoio aos testes: respostas no formato de docs/api.md e um fetch falso controlável.
import { vi } from 'vitest'
import type { Servidor, ServidoresResponse } from './types'

export const SERVIDOR_ATIVO: Servidor = {
  id: 1048213,
  nome: 'MARIA DA SILVA',
  situacao: 'ativo',
  cargo: 'ANALISTA DE FINANCAS E CONTROLE',
  orgao: 'CONTROLADORIA-GERAL DA UNIAO',
  sigla_orgao: null,
  uf: 'DF',
  valor: 19090.67,
}

export const SERVIDOR_APOSENTADO: Servidor = {
  id: 1503377,
  nome: 'MARIA DA SILVA',
  situacao: 'aposentado',
  cargo: null,
  orgao: 'MINISTERIO DA AGRICULTURA E PECUARIA',
  sigla_orgao: 'MAPA',
  uf: null,
  valor: 7006.78,
}

export function corpoServidores(
  data: Servidor[] = [SERVIDOR_ATIVO, SERVIDOR_APOSENTADO],
  meta: Partial<ServidoresResponse['meta']> = {},
): ServidoresResponse {
  return {
    data,
    meta: { total: data.length, total_exato: true, page: 1, per_page: 20, total_pages: 1, ...meta },
  }
}

export function respostaJson(status: number, corpo: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
  })
}

export function respostaTexto(status: number, corpo: string): Response {
  return new Response(corpo, { status, headers: { 'Content-Type': 'text/html' } })
}

export function erroApi(status: number, code: string, message: string, headers: Record<string, string> = {}): Response {
  return respostaJson(status, { error: { code, message } }, headers)
}

export interface Pedido {
  url: string
  init: RequestInit | undefined
  signal: AbortSignal
  responder: (response: Response) => void
  falhar: (erro: unknown) => void
}

/**
 * Troca o fetch global por um que deixa cada chamada pendente até o teste responder.
 * Como o fetch de verdade, rejeita com AbortError quando o signal é cancelado.
 */
export function fetchPendente() {
  const pedidos: Pedido[] = []
  const fetchMock = vi.fn(
    (input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((resolve, reject) => {
        const signal = init?.signal ?? new AbortController().signal
        signal.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')))
        pedidos.push({ url: String(input), init, signal, responder: resolve, falhar: reject })
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, pedidos }
}

/** Troca o fetch global por um que responde na hora, criando a resposta a cada chamada. */
export function fetchRespondendo(criarResposta: () => Response) {
  const fetchMock = vi.fn(() => Promise.resolve(criarResposta()))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
