import { formatSimilaridade } from './format'
import { NaoInformado } from './NaoInformado'

const PORCENTAGEM = 100

/** Semelhança da busca parecida: barra só visual e o número, de 0,00 a 1,00. */
export function Semelhanca({ valor }: { valor: number | undefined }) {
  if (valor === undefined) return <NaoInformado />
  return (
    <div className="semelhanca">
      <div className="semelhanca__barra" aria-hidden="true">
        <span style={{ width: `${valor * PORCENTAGEM}%` }} />
      </div>
      <span className="num">{formatSimilaridade(valor)}</span>
    </div>
  )
}
