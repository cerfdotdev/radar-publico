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
