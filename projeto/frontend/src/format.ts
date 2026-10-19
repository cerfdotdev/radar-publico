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
