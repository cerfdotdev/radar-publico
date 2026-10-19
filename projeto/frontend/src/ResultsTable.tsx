import { formatCurrency } from './format'
import { NaoInformado } from './NaoInformado'
import { SituacaoPill } from './SituacaoPill'
import type { Servidor } from './types'

/** Resultados em tabela (acima de 640 px). */
export function ResultsTable({ servidores }: { servidores: Servidor[] }) {
  return (
    <div className="tabela-caixa">
      <table className="tabela">
        <caption className="sr-only">Servidores encontrados</caption>
        <thead>
          <tr>
            <th scope="col">Nome</th>
            <th scope="col">Situação</th>
            <th scope="col">Cargo</th>
            <th scope="col">Órgão</th>
            <th scope="col">UF</th>
            <th scope="col" className="direita">
              Valor (R$)
            </th>
          </tr>
        </thead>
        <tbody>
          {servidores.map((servidor) => (
            <tr key={servidor.id}>
              <th scope="row" className="fonte-dado">
                {servidor.nome}
              </th>
              <td>
                <SituacaoPill situacao={servidor.situacao} />
              </td>
              <td className="secundario fonte-dado">{servidor.cargo ?? <NaoInformado />}</td>
              <td className="secundario fonte-dado">
                {servidor.sigla_orgao === null ? servidor.orgao : `${servidor.orgao} (${servidor.sigla_orgao})`}
              </td>
              <td className="num secundario">{servidor.uf ?? <NaoInformado />}</td>
              <td className="num direita">
                {servidor.valor === null ? <NaoInformado /> : formatCurrency(servidor.valor)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
