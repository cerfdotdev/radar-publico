// Regras do parâmetro `nome` (docs/api.md), conferidas antes de chamar a API.

/** Limites de tamanho do contrato, contados depois da normalização. */
export const NOME_MIN_CHARS = 2
export const NOME_MAX_CHARS = 100

// Depois da normalização, como no backend: só letras sem acento, espaço, ' . e -.
const NOME_PERMITIDO = /^[A-Z .'-]+$/
const SEQUENCIA_PROIBIDA = '--'

/** "  Maria   da Silva " -> "Maria da Silva". Mantém acentos e maiúsculas como digitados. */
export function limparNome(nome: string): string {
  return nome.trim().split(/\s+/).join(' ')
}

/** "José  d'Ávila" -> "JOSE D'AVILA": sem acento, em maiúsculas e com espaços simples. */
export function normalizarNome(nome: string): string {
  return limparNome(nome.normalize('NFKD').replace(/\p{M}/gu, '')).toUpperCase()
}

/** Mensagem do erro de validação, ou null se o nome pode ser enviado. */
export function validarNome(nome: string): string | null {
  const normalizado = normalizarNome(nome)
  if (normalizado.length === 0) {
    return 'Informe um nome para pesquisar.'
  }
  if (normalizado.length < NOME_MIN_CHARS) {
    return `O nome deve ter pelo menos ${NOME_MIN_CHARS} caracteres.`
  }
  if (normalizado.length > NOME_MAX_CHARS) {
    return `O nome deve ter no máximo ${NOME_MAX_CHARS} caracteres.`
  }
  if (!NOME_PERMITIDO.test(normalizado)) {
    return "Use só letras, espaços, apóstrofo ('), ponto (.) e hífen (-)."
  }
  if (normalizado.includes(SEQUENCIA_PROIBIDA)) {
    return 'Não use dois hífens seguidos (--).'
  }
  return null
}
