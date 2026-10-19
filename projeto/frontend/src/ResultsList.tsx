import { formatCurrency } from './format'
import { NaoInformado } from './NaoInformado'
import { SituacaoPill } from './SituacaoPill'
import type { Servidor } from './types'

/** Resultados em lista (até 640 px), no lugar da tabela. */
export function ResultsList({ servidores }: { servidores: Servidor[] }) {
  return (
    <ul className="lista" aria-label="Servidores encontrados">
      {servidores.map((servidor) => {
        // Só as partes que existem, para não sobrar um " · " solto quando o cargo é null.
        const detalhes = [servidor.cargo, servidor.sigla_orgao ?? servidor.orgao]
          .filter((parte) => parte !== null)
          .join(' · ')
        return (
          <li key={servidor.id}>
            <div className="lista-item">
              <div className="lista__linha">
                <strong className="fonte-dado">{servidor.nome}</strong>
                <span className="num">
                  {servidor.valor === null ? <NaoInformado /> : `R$ ${formatCurrency(servidor.valor)}`}
                </span>
              </div>
              <span className="aux fonte-dado">{detalhes}</span>
              <div className="lista__meta">
                <SituacaoPill situacao={servidor.situacao} />
                <span>UF {servidor.uf ?? <NaoInformado />}</span>
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
