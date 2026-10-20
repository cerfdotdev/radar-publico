// Validação dos filtros de docs/api.md, conferida antes de chamar a API.
import { NOME_MAX_CHARS, NOME_MIN_CHARS, normalizarNome, SEQUENCIA_PROIBIDA, validarNome } from './nome'
import type { Busca, CampoBusca, ModoBusca } from './types'

/** `limit` da busca parecida: de 1 a 100, padrão 100 (docs/api.md). */
export const LIMITE_MIN = 1
export const LIMITE_MAX = 100
export const LIMITE_PADRAO = 100
/** O padrão de `similar` precisa de pelo menos 3 letras fora dos `%`. */
export const SIMILAR_MIN_LETRAS = 3

/** As 27 UFs aceitas pela API. */
export const UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT',
  'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const

export interface ErroBusca {
  campo: CampoBusca
  mensagem: string
}

// Depois da normalização, como no backend. Similar aceita também o curinga %;
// cargo e órgão, dígitos, barra, parênteses e vírgula.
const SIMILAR_PERMITIDO = /^[A-Z .'%-]+$/
const TEXTO_PERMITIDO = /^[A-Z0-9 /(),.'-]+$/
const LETRA = /[A-Z]/g

/**
 * A API ainda ignora cargo, órgão e UF quando recebe `similar` (a consulta por
 * semelhança só olha o nome). Enquanto for assim, a busca parecida não envia esses
 * filtros e o formulário os mostra desativados, para a tela não sugerir um filtro
 * que não foi aplicado.
 */
export function aceitaFiltros(modo: ModoBusca): boolean {
  return modo === 'exato'
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
  if ((normalizado.match(LETRA)?.length ?? 0) < SIMILAR_MIN_LETRAS) {
    return `Digite pelo menos ${SIMILAR_MIN_LETRAS} letras além dos %.`
  }
  return null
}

// Partes do nome que o padrão parecido sugerido deixa de fora (docs/design/estados.html).
const CONECTIVOS = new Set(['DA', 'DAS', 'DE', 'DO', 'DOS', 'E'])

/**
 * Nome exato sem resultado como padrão parecido: "João da Silva" -> "%JOAO%SILVA%".
 * Null quando o padrão não passaria na validação (ex.: menos de 3 letras).
 */
export function padraoParecido(nome: string): string | null {
  const partes = normalizarNome(nome)
    .split(' ')
    .filter((parte) => parte !== '' && !CONECTIVOS.has(parte))
  const padrao = `%${partes.join('%')}%`
  return validarSimilar(padrao) === null ? padrao : null
}

/** Cargo e órgão: texto opcional, com as mesmas regras de tamanho do nome. */
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
    return "Use só letras, números, espaços, apóstrofo ('), ponto (.), hífen (-), barra (/), parênteses e vírgula."
  }
  if (normalizado.includes(SEQUENCIA_PROIBIDA)) {
    return 'Não use dois hífens seguidos (--).'
  }
  return null
}

export function validarLimite(limite: number): string | null {
  if (Number.isInteger(limite) && limite >= LIMITE_MIN && limite <= LIMITE_MAX) return null
  return `O limite deve ser um número inteiro de ${LIMITE_MIN} a ${LIMITE_MAX}.`
}

export function validarUf(uf: string): string | null {
  if (uf === '' || (UFS as readonly string[]).includes(uf)) return null
  return 'Escolha uma UF válida.'
}

/** Primeiro erro da busca, na ordem dos campos na tela, ou null se pode ser enviada. */
export function validarBusca(busca: Busca): ErroBusca | null {
  if (!aceitaFiltros(busca.modo)) {
    const mensagem = validarSimilar(busca.termo)
    if (mensagem !== null) return { campo: 'termo', mensagem }
    const mensagemLimite = validarLimite(busca.limite)
    return mensagemLimite === null ? null : { campo: 'limite', mensagem: mensagemLimite }
  }

  const semFiltro =
    busca.termo.trim() === '' && busca.cargo.trim() === '' && busca.orgao.trim() === '' && busca.uf === ''
  if (semFiltro) {
    return { campo: 'termo', mensagem: 'Informe um nome ou pelo menos um filtro: cargo, órgão ou UF.' }
  }

  if (busca.termo.trim() !== '') {
    const mensagem = validarNome(busca.termo)
    if (mensagem !== null) return { campo: 'termo', mensagem }
  }

  for (const [campo, valor, rotulo] of [
    ['cargo', busca.cargo, 'cargo'],
    ['orgao', busca.orgao, 'órgão'],
  ] as const) {
    const mensagem = validarTexto(valor, rotulo)
    if (mensagem !== null) return { campo, mensagem }
  }

  const mensagemUf = validarUf(busca.uf)
  return mensagemUf === null ? null : { campo: 'uf', mensagem: mensagemUf }
}
