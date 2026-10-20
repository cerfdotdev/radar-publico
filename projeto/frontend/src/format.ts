// Números no formato brasileiro (docs/design/README.md).

const currencyFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const integerFormatter = new Intl.NumberFormat('pt-BR')

/** Travessão para valor ausente, como nas colunas sem dado. */
export const SEM_VALOR = '—'

/** 19090.67 -> "19.090,67". Valor não finito vira travessão, nunca "NaN". */
export function formatCurrency(value: number): string {
  return Number.isFinite(value) ? currencyFormatter.format(value) : SEM_VALOR
}

/** 10000 -> "10.000". */
export function formatInteger(value: number): string {
  return integerFormatter.format(value)
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
