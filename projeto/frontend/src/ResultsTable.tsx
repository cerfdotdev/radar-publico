import { formatCurrency } from './format'
import { NaoInformado } from './NaoInformado'
import { Semelhanca } from './Semelhanca'
import { SituacaoPill } from './SituacaoPill'
import type { Servidor } from './types'

interface ResultsTableProps {
  servidores: Servidor[]
  /** Busca parecida: coluna Semelhança, na ordem da API (mais parecido primeiro). */
  similar: boolean
}

/** Resultados em tabela (acima de 640 px). */
export function ResultsTable({ servidores, similar }: ResultsTableProps) {
  return (
    <div className="tabela-caixa">
      <table className="tabela">
        <caption className="sr-only">Servidores encontrados</caption>
        <thead>
          <tr>
            <th scope="col">Nome</th>
            {similar && (
              <th scope="col" aria-sort="descending">
                Semelhança
              </th>
            )}
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
              {similar && (
                <td>
                  <Semelhanca valor={servidor.similaridade} />
                </td>
              )}
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
