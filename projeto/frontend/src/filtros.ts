// Validação dos filtros de docs/api.md, conferida antes de chamar a API.
import { NOME_MAX_CHARS, NOME_MIN_CHARS, normalizarNome, validarNome } from './nome'
import type { Busca } from './types'

export const LIMITE_MIN = 1
export const LIMITE_MAX = 100
export const LIMITE_PADRAO = 100

/** As 27 UFs aceitas pela API. */
export const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT',
  'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const

export type CampoBusca = 'termo' | 'limite' | 'cargo' | 'orgao' | 'uf'

export interface ErroBusca {
  campo: CampoBusca
  mensagem: string
}

const SEQUENCIA_PROIBIDA = '--'
// Depois da normalização, como no backend. Similar aceita também o curinga %.
const SIMILAR_PERMITIDO = /^[A-Z .'%-]+$/
const TEXTO_PERMITIDO = /^[A-Z0-9 /(),.'-]+$/u
const LETRAS = /[A-Z]/g

/** "  Maria   da Silva " -> "Maria da Silva"; aceita % no padrão de similaridade. */
export function limparTermo(termo: string): string {
  return termo.trim().split(/\s+/).join(' ')
}

/** Mensagem do erro do padrão de similaridade, ou null se pode ser enviado. */
export function validarSimilar(termo: string): string | null {
  const normalizado = normalizarNome(termo)
  if (normalizado.length === 0) {
    return 'Informe um nome parecido para pesquisar.'
  }
  if (normalizado.length < NOME_MIN_CHARS) {
    return `O nome parecido deve ter pelo menos ${NOME_MIN_CHARS} caracteres.`
  }
  if (normalizado.length > NOME_MAX_CHARS) {
    return `O nome parecido deve ter no máximo ${NOME_MAX_CHARS} caracteres.`
  }
  if (!SIMILAR_PERMITIDO.test(normalizado)) {
    return "Use só letras, espaços, apóstrofo ('), ponto (.), hífen (-) e o curinga (%)."
  }
  if (normalizado.includes(SEQUENCIA_PROIBIDA)) {
    return 'Não use dois hífens seguidos (--).'
  }
  if ((normalizado.match(LETRAS)?.length ?? 0) < 3) {
    return 'Use pelo menos 3 letras fora dos %.'
  }
  return null
}

/** Cargo e órgão: texto opcional, de 2 a 100 caracteres. */
export function validarTexto(valor: string, rotulo: string): string | null {
  const normalizado = normalizarNome(valor)
  if (normalizado.length === 0) return null
  if (normalizado.length < NOME_MIN_CHARS) {
    return `O ${rotulo} deve ter pelo menos ${NOME_MIN_CHARS} caracteres.`
  }
  if (normalizado.length > NOME_MAX_CHARS) {
    return `O ${rotulo} deve ter no máximo ${NOME_MAX_CHARS} caracteres.`
  }
  if (!TEXTO_PERMITIDO.test(normalizado)) {
    return `Use só letras, números, espaços, apóstrofo ('), ponto (.), hífen (-), barra (/), parênteses e vírgula.`
  }
  if (normalizado.includes(SEQUENCIA_PROIBIDA)) {
    return 'Não use dois hífens seguidos (--).'
  }
  return null
}

export function validarUf(uf: string): string | null {
  if (uf === '' || (UFS as readonly string[]).includes(uf)) return null
  return 'Escolha uma UF válida.'
}

export function validarBusca(busca: Busca): ErroBusca | null {
  const semFiltro =
    busca.termo.trim() === '' && busca.cargo.trim() === '' && busca.orgao.trim() === '' && busca.uf === ''
  if (semFiltro) {
    return { campo: 'termo', mensagem: 'Informe um nome para pesquisar.' }
  }

  if (busca.termo.trim() !== '') {
    const mensagem = busca.modo === 'similar' ? validarSimilar(busca.termo) : validarNome(busca.termo)
    if (mensagem !== null) return { campo: 'termo', mensagem }
  }

  if (busca.modo === 'similar' && !Number.isInteger(busca.limite)) {
    return { campo: 'limite', mensagem: 'Informe um limite inteiro.' }
  }
  if (busca.modo === 'similar' && (busca.limite < LIMITE_MIN || busca.limite > LIMITE_MAX)) {
    return { campo: 'limite', mensagem: `O limite deve estar entre ${LIMITE_MIN} e ${LIMITE_MAX}.` }
  }

  for (const [rotulo, valor, campo] of [
    ['cargo', busca.cargo, 'cargo'],
    ['órgão', busca.orgao, 'orgao'],
  ] as const) {
    const mensagem = validarTexto(valor, rotulo)
    if (mensagem !== null) return { campo, mensagem }
  }

  const mensagemUf = validarUf(busca.uf)
  if (mensagemUf !== null) return { campo: 'uf', mensagem: mensagemUf }

  return null
}
