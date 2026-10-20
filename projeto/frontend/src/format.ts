// Números no formato brasileiro (docs/design/README.md).

// Duas casas decimais: valores em reais e a semelhança da busca parecida.
const twoDecimalsFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const integerFormatter = new Intl.NumberFormat('pt-BR')

/** Travessão para valor ausente, como nas colunas sem dado. */
export const SEM_VALOR = '—'

/** 19090.67 -> "19.090,67". Valor não finito vira travessão, nunca "NaN". */
export function formatCurrency(value: number): string {
  return Number.isFinite(value) ? twoDecimalsFormatter.format(value) : SEM_VALOR
}

/** 10000 -> "10.000". */
export function formatInteger(value: number): string {
  return integerFormatter.format(value)
}

/** 0.8571 -> "0,86": semelhança de 0 a 1 da busca parecida. */
export function formatSimilaridade(value: number): string {
  return Number.isFinite(value) ? twoDecimalsFormatter.format(value) : SEM_VALOR
}

/** "1990-07-02" -> "02/07/1990". Fora do formato ISO, devolve como veio. */
export function formatDate(value: string): string {
  const partes = value.split('-')
  if (partes.length !== 3 || partes.some((parte) => !/^\d+$/.test(parte))) return value
  const [ano, mes, dia] = partes
  return `${dia}/${mes}/${ano}`
}

/** "2026-05" -> "05/2026". Fora do formato, devolve como veio. */
export function formatReference(value: string): string {
  const partes = value.split('-')
  if (partes.length !== 2 || partes.some((parte) => !/^\d+$/.test(parte))) return value
  const [ano, mes] = partes
  return `${mes}/${ano}`
}
