// Cliente de GET /api/servidores (docs/api.md): requisição, tempo limite e validação da resposta.
import type { ApiError, CampoBusca, Meta, Servidor, ServidorDetalhe, ServidoresResponse } from './types'

export const SERVIDORES_URL = '/api/servidores'
/**
 * Tempo máximo esperando a busca. Fica acima dos 15 s de proxy_read_timeout do nginx,
 * para o 504 TEMPO_ESGOTADO do nginx chegar antes de o navegador desistir.
 */
export const SEARCH_TIMEOUT_MS = 20_000
/** A API para de contar em 10.000 resultados (meta.total_exato = false). */
export const TOTAL_CAP = 10_000
const MS_PER_SECOND = 1000

const HttpStatus = {
  BAD_REQUEST: 400,
  NOT_FOUND: 404,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_SERVER_ERROR: 500,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503,
  GATEWAY_TIMEOUT: 504,
} as const

/** O que a tela mostra quando a busca falha. */
export interface Falha {
  /** 'info' para limites de uso (429/503), que não são erro de quem busca. */
  tom: 'info' | 'erro'
  titulo: string
  texto: string
}

export type SearchOutcome =
  | { kind: 'ok'; servidores: Servidor[]; meta: Meta }
  | { kind: 'empty' }
  /** 400, ou cargo e órgão sem correspondente: a mensagem aparece no próprio campo. */
  | { kind: 'invalid'; campo: CampoBusca; message: string }
  /** 404 PAGINA_INEXISTENTE: link velho; `ultimaPagina` vem da mensagem da API, se ela disser. */
  | { kind: 'no-page'; ultimaPagina: number | null }
  | { kind: 'error'; falha: Falha }

const TENTE_DE_NOVO = 'Tente de novo em instantes.'

const FALHA_SEM_CONEXAO: Falha = {
  tom: 'erro',
  titulo: 'Não foi possível conectar à API',
  texto: 'Confira sua conexão com a internet e tente de novo.',
}
const FALHA_TEMPO_LIMITE: Falha = {
  tom: 'erro',
  titulo: `A API não respondeu em ${SEARCH_TIMEOUT_MS / MS_PER_SECOND} segundos`,
  texto: TENTE_DE_NOVO,
}
const FALHA_NAO_JSON: Falha = {
  tom: 'erro',
  titulo: 'A API respondeu, mas não em JSON',
  texto: `A resposta não veio no formato esperado. ${TENTE_DE_NOVO}`,
}
const FALHA_FORMATO: Falha = {
  tom: 'erro',
  titulo: 'Resposta inesperada da API',
  texto: `Os dados vieram fora do formato combinado. ${TENTE_DE_NOVO}`,
}
export const FALHA_INESPERADA: Falha = {
  tom: 'erro',
  titulo: 'Não foi possível concluir a busca',
  texto: TENTE_DE_NOVO,
}

// Código do contrato para cada status quando o corpo não traz o JSON de erro
// (ex.: página HTML de um proxy no caminho).
const CODIGO_POR_STATUS: Partial<Record<number, string>> = {
  [HttpStatus.TOO_MANY_REQUESTS]: 'MUITAS_REQUISICOES',
  [HttpStatus.INTERNAL_SERVER_ERROR]: 'ERRO_INTERNO',
  [HttpStatus.BAD_GATEWAY]: 'SERVIDOR_INDISPONIVEL',
  [HttpStatus.SERVICE_UNAVAILABLE]: 'SERVIDOR_OCUPADO',
  [HttpStatus.GATEWAY_TIMEOUT]: 'TEMPO_ESGOTADO',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringOrNull(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isSimilaridade(value: unknown): value is number {
  return typeof value === 'number' && value >= 0 && value <= 1
}

function parseServidor(value: unknown): Servidor | null {
  if (!isRecord(value)) return null
  const { id, nome, situacao, cargo, orgao, sigla_orgao, uf, valor, similaridade } = value
  if (
    typeof id !== 'number' ||
    !Number.isSafeInteger(id) ||
    typeof nome !== 'string' ||
    (situacao !== 'ativo' && situacao !== 'aposentado') ||
    !isStringOrNull(cargo) ||
    typeof orgao !== 'string' ||
    !isStringOrNull(sigla_orgao) ||
    !isStringOrNull(uf) ||
    !(valor === null || (typeof valor === 'number' && Number.isFinite(valor))) ||
    !(similaridade === undefined || isSimilaridade(similaridade))
  ) {
    return null
  }
  const servidor: Servidor = { id, nome, situacao, cargo, orgao, sigla_orgao, uf, valor }
  return similaridade === undefined ? servidor : { ...servidor, similaridade }
}

// Campos que só o detalhe traz; todos texto ou null (datas em AAAA-MM-DD).
const CAMPOS_DETALHE = [
  'codigo_carreira',
  'tipo_aposentadoria',
  'fundamento_legal',
  'portaria',
  'data_aposentadoria',
  'forma_ingresso',
  'data_ingresso',
  'referencia',
] as const satisfies readonly (keyof ServidorDetalhe)[]

function parseServidorDetalhe(value: unknown): ServidorDetalhe | null {
  const servidor = parseServidor(value)
  if (servidor === null || !isRecord(value)) return null
  const detalhe: Partial<ServidorDetalhe> = {}
  for (const campo of CAMPOS_DETALHE) {
    const valor = value[campo]
    if (!isStringOrNull(valor)) return null
    detalhe[campo] = valor
  }
  return { ...servidor, ...(detalhe as Pick<ServidorDetalhe, (typeof CAMPOS_DETALHE)[number]>) }
}

function parseMeta(value: unknown): Meta | null {
  if (!isRecord(value)) return null
  const { total, total_exato, page, per_page, total_pages } = value
  if (
    !isCount(total) ||
    typeof total_exato !== 'boolean' ||
    !isCount(page) ||
    !isCount(per_page) ||
    !isCount(total_pages)
  ) {
    return null
  }
  return { total, total_exato, page, per_page, total_pages }
}

/**
 * Confere a resposta 200 contra o contrato. Qualquer campo faltando ou de outro tipo
 * invalida a resposta inteira (null); campos a mais são ignorados.
 */
export function parseServidoresResponse(json: unknown): ServidoresResponse | null {
  if (!isRecord(json) || !Array.isArray(json.data)) return null
  const meta = parseMeta(json.meta)
  if (meta === null) return null
  const data: Servidor[] = []
  for (const item of json.data) {
    const servidor = parseServidor(item)
    if (servidor === null) return null
    data.push(servidor)
  }
  return { data, meta }
}

/** Confere a resposta de GET /api/servidores/<id> contra o contrato. */
export function parseServidorDetalheResponse(json: unknown): ServidorDetalhe | null {
  if (!isRecord(json)) return null
  return parseServidorDetalhe(json.data)
}

/** {"error": {"code", "message"}} do contrato, ou null se o corpo for outra coisa. */
export function parseApiError(json: unknown): ApiError | null {
  if (!isRecord(json) || !isRecord(json.error)) return null
  const { code, message } = json.error
  return typeof code === 'string' && typeof message === 'string' ? { code, message } : null
}

/** Retry-After em segundos. A forma de data HTTP é ignorada. */
function lerRetryAfter(headers: Headers): number | null {
  const valor = headers.get('Retry-After')?.trim()
  return valor !== undefined && /^\d+$/.test(valor) ? Number(valor) : null
}

function falhaHttp(status: number, erro: ApiError | null, retryAfter: number | null): Falha {
  const espera =
    retryAfter === null
      ? TENTE_DE_NOVO
      : `Você pode buscar de novo em ${retryAfter} ${retryAfter === 1 ? 'segundo' : 'segundos'}.`
  switch (erro?.code ?? CODIGO_POR_STATUS[status]) {
    case 'MUITAS_REQUISICOES':
      return {
        tom: 'info',
        titulo: 'Muitas buscas em pouco tempo',
        texto: `Para manter o serviço no ar para todos, limitamos buscas seguidas. ${espera}`,
      }
    case 'SERVIDOR_OCUPADO':
      return {
        tom: 'info',
        titulo: 'O serviço está ocupado',
        texto: `Há muitas buscas ao mesmo tempo. ${espera}`,
      }
    case 'SERVIDOR_INDISPONIVEL':
      return { tom: 'erro', titulo: 'A API está fora do ar', texto: TENTE_DE_NOVO }
    case 'TEMPO_ESGOTADO':
      // docs/design/estados.html: o 504 explica a causa provável e o que fazer.
      return {
        tom: 'erro',
        titulo: 'A busca demorou demais e foi interrompida',
        texto:
          'Buscas muito amplas, como um padrão curto (%SILVA%) ou só uma UF, comparam centenas de milhares de vínculos. Acrescente outra parte do nome ou outro filtro e tente de novo.',
      }
    case 'ERRO_INTERNO':
      return { tom: 'erro', titulo: 'Algo deu errado do nosso lado', texto: TENTE_DE_NOVO }
    default:
      return {
        ...FALHA_INESPERADA,
        texto: erro?.message ?? `A API respondeu com erro (HTTP ${status}).`,
      }
  }
}

const NAO_JSON = Symbol('corpo que não é JSON')

function lerJson(corpo: string): unknown {
  try {
    return JSON.parse(corpo)
  } catch {
    return NAO_JSON
  }
}

// Parâmetro da query -> campo do formulário. As mensagens de 400 da API começam pelo
// parâmetro entre aspas ("'limit' deve estar entre 1 e 100."); sem ele, vale o nome.
const CAMPO_DO_PARAMETRO = new Map<string, CampoBusca>([
  ['nome', 'termo'],
  ['similar', 'termo'],
  ['limit', 'limite'],
  ['cargo', 'cargo'],
  ['orgao', 'orgao'],
  ['uf', 'uf'],
])
const PARAMETRO_DA_MENSAGEM = /^'([a-z_]+)'/
const TOTAL_DE_PAGINAS_NA_MENSAGEM = /tem (\d+) página/

/** Erro que é de um campo do formulário (docs/design/estados.html, "Entrada inválida"), ou null. */
function erroDeCampo(
  status: number,
  erro: ApiError,
  parametros: ParametrosBusca,
): Extract<SearchOutcome, { kind: 'invalid' }> | null {
  if (status === HttpStatus.NOT_FOUND && erro.code === 'CARGO_NAO_ENCONTRADO') {
    const texto = parametros.cargo ?? ''
    return {
      kind: 'invalid',
      campo: 'cargo',
      message: `Nenhum cargo contém “${texto}”. Confira a grafia ou use só uma parte do nome do cargo.`,
    }
  }
  if (status === HttpStatus.NOT_FOUND && erro.code === 'ORGAO_NAO_ENCONTRADO') {
    const texto = parametros.orgao ?? ''
    return {
      kind: 'invalid',
      campo: 'orgao',
      message: `Nenhum órgão tem “${texto}” no nome ou na sigla. Confira a grafia ou use a sigla, como INSS.`,
    }
  }
  if (status !== HttpStatus.BAD_REQUEST) return null
  if (erro.code === 'UF_INVALIDA') return { kind: 'invalid', campo: 'uf', message: erro.message }
  const parametro = PARAMETRO_DA_MENSAGEM.exec(erro.message)?.[1] ?? ''
  return { kind: 'invalid', campo: CAMPO_DO_PARAMETRO.get(parametro) ?? 'termo', message: erro.message }
}

function interpretarResposta(response: Response, corpo: string, parametros: ParametrosBusca): SearchOutcome {
  const json = lerJson(corpo)
  if (response.ok) {
    if (json === NAO_JSON) return { kind: 'error', falha: FALHA_NAO_JSON }
    const dados = parseServidoresResponse(json)
    if (dados === null) return { kind: 'error', falha: FALHA_FORMATO }
    // A API responde 404 NAO_ENCONTRADO quando não acha ninguém; lista vazia vale o mesmo.
    return dados.data.length === 0
      ? { kind: 'empty' }
      : { kind: 'ok', servidores: dados.data, meta: dados.meta }
  }

  const erro = parseApiError(json)
  if (erro?.code === 'NAO_ENCONTRADO') return { kind: 'empty' }
  if (erro?.code === 'PAGINA_INEXISTENTE') {
    // "A página 40 não existe; esta busca tem 3 página(s)."
    const total = TOTAL_DE_PAGINAS_NA_MENSAGEM.exec(erro.message)?.[1]
    return { kind: 'no-page', ultimaPagina: total === undefined ? null : Number(total) }
  }
  const invalido = erro === null ? null : erroDeCampo(response.status, erro, parametros)
  if (invalido !== null) return invalido
  return { kind: 'error', falha: falhaHttp(response.status, erro, lerRetryAfter(response.headers)) }
}

/** Parâmetros de GET /api/servidores; filtros vazios não entram na query. */
export interface ParametrosBusca {
  nome?: string
  similar?: string
  limit?: number
  cargo?: string
  orgao?: string
  uf?: string
  page?: number
  per_page?: number
}

function montarQuery(parametros: ParametrosBusca): string {
  const query = new URLSearchParams()
  if (parametros.nome) query.set('nome', parametros.nome)
  if (parametros.similar) query.set('similar', parametros.similar)
  if (parametros.limit !== undefined) query.set('limit', String(parametros.limit))
  if (parametros.cargo) query.set('cargo', parametros.cargo)
  if (parametros.orgao) query.set('orgao', parametros.orgao)
  if (parametros.uf) query.set('uf', parametros.uf)
  if (parametros.page !== undefined) query.set('page', String(parametros.page))
  if (parametros.per_page !== undefined) query.set('per_page', String(parametros.per_page))
  return query.toString()
}

type Pedido = { kind: 'resposta'; response: Response; corpo: string } | { kind: 'falha'; falha: Falha }

/**
 * GET em JSON com tempo limite. Falha de rede e tempo esgotado viram uma Falha para a
 * tela; só rejeita (AbortError) quando `signal` cancela o pedido.
 */
async function pedir(url: string, signal: AbortSignal): Promise<Pedido> {
  if (signal.aborted) throw new DOMException('Busca cancelada.', 'AbortError')

  // Controller próprio para os dois motivos de parar: o tempo limite (vira erro na tela)
  // e o cancelamento por quem chamou (busca nova ou tela fechada, que é ignorado).
  const controller = new AbortController()
  const cancelar = () => controller.abort()
  signal.addEventListener('abort', cancelar)
  let expirou = false
  const timer = setTimeout(() => {
    expirou = true
    controller.abort()
  }, SEARCH_TIMEOUT_MS)

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    return { kind: 'resposta', response, corpo: await response.text() }
  } catch (erro) {
    if (signal.aborted) throw erro
    return { kind: 'falha', falha: expirou ? FALHA_TEMPO_LIMITE : FALHA_SEM_CONEXAO }
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', cancelar)
  }
}

/**
 * Busca servidores pelo nome exato ou por filtros combinados. Nunca rejeita por erro
 * de rede, HTTP ou formato: tudo vira um SearchOutcome. Só rejeita (AbortError)
 * quando `signal` cancela a busca.
 */
export async function buscarServidores(
  busca: string | ParametrosBusca,
  signal: AbortSignal,
): Promise<SearchOutcome> {
  const parametros: ParametrosBusca = typeof busca === 'string' ? { nome: busca } : busca
  const pedido = await pedir(`${SERVIDORES_URL}?${montarQuery(parametros)}`, signal)
  if (pedido.kind === 'falha') return { kind: 'error', falha: pedido.falha }
  return interpretarResposta(pedido.response, pedido.corpo, parametros)
}

export type DetailOutcome =
  | { kind: 'ok'; servidor: ServidorDetalhe }
  | { kind: 'error'; falha: Falha }

/**
 * Detalhe de um vínculo (GET /api/servidores/<id>). Como a busca, nunca rejeita por
 * erro de rede, HTTP ou formato; só rejeita quando `signal` cancela.
 */
export async function buscarServidor(id: number, signal: AbortSignal): Promise<DetailOutcome> {
  const pedido = await pedir(`${SERVIDORES_URL}/${id}`, signal)
  if (pedido.kind === 'falha') return { kind: 'error', falha: pedido.falha }
  const { response, corpo } = pedido

  const json = lerJson(corpo)
  if (response.ok) {
    if (json === NAO_JSON) return { kind: 'error', falha: FALHA_NAO_JSON }
    const servidor = parseServidorDetalheResponse(json)
    if (servidor === null) return { kind: 'error', falha: FALHA_FORMATO }
    return { kind: 'ok', servidor }
  }

  const erro = parseApiError(json)
  return { kind: 'error', falha: falhaHttp(response.status, erro, lerRetryAfter(response.headers)) }
}
