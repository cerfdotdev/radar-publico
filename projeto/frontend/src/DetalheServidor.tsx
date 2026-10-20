import { useEffect, useState } from 'react'
import { buscarServidor, type DetailOutcome } from './api'
import { formatCurrency, formatDate, formatReference } from './format'
import { NaoInformado } from './NaoInformado'
import { SituacaoPill } from './SituacaoPill'
import type { Servidor, ServidorDetalhe } from './types'

type EstadoDetalhe = { kind: 'carregando' } | DetailOutcome

/** Campos que só existem no detalhe; usados enquanto a requisição não chega. */
const DETALHE_AUSENTE: Omit<ServidorDetalhe, keyof Servidor> = {
  codigo_carreira: null,
  tipo_aposentadoria: null,
  fundamento_legal: null,
  portaria: null,
  data_aposentadoria: null,
  forma_ingresso: null,
  data_ingresso: null,
  referencia: null,
}

/** Resultado único da busca: ficha completa do vínculo (docs/design/detalhe.html). */
export function DetalheServidor({ resumo }: { resumo: Servidor }) {
  const [estado, setEstado] = useState<EstadoDetalhe>({ kind: 'carregando' })

  useEffect(() => {
    const controller = new AbortController()
    buscarServidor(resumo.id, controller.signal).then(
      (resultado) => {
        if (!controller.signal.aborted) setEstado(resultado)
      },
      () => {
        // Cancelamento não muda a tela; a ficha segue com os dados da lista.
      },
    )
    return () => controller.abort()
  }, [resumo.id])

  const detalhe = estado.kind === 'ok' ? estado.servidor : null
  const servidor: ServidorDetalhe = detalhe ?? { ...resumo, ...DETALHE_AUSENTE }
  const aposentado = servidor.situacao === 'aposentado'

  return (
    <section className="detalhe" aria-labelledby="detalhe-titulo" aria-busy={estado.kind === 'carregando'}>
      <div className="cabecalho-vinculo">
        <div className="cabecalho-vinculo__id">
          <SituacaoPill situacao={servidor.situacao} />
          <h1 className="titulo-pagina" id="detalhe-titulo">
            {servidor.nome}
          </h1>
          <p className="fonte-dado detalhe__resumo">
            {servidor.cargo ?? 'Cargo não informado'} · {servidor.orgao}
            {servidor.sigla_orgao === null ? '' : ` (${servidor.sigla_orgao})`}
          </p>
        </div>
        <div className="cabecalho-vinculo__valor">
          <span className="aux">{aposentado ? 'Valor da aposentadoria' : 'Remuneração'}</span>
          <span className="valor-grande">
            {servidor.valor === null ? <NaoInformado /> : `R$ ${formatCurrency(servidor.valor)}`}
          </span>
          {servidor.referencia !== null && (
            <span className="aux">Referência {formatReference(servidor.referencia)}</span>
          )}
        </div>
      </div>

      <div className="colunas">
        <section aria-labelledby="sec-vinculo">
          <h3 className="subtitulo" id="sec-vinculo">
            Vínculo
          </h3>
          <dl className="dados">
            <div>
              <dt>Cargo</dt>
              <dd>{servidor.cargo ?? <NaoInformado />}</dd>
            </div>
            <div>
              <dt>Órgão</dt>
              <dd>{servidor.orgao}</dd>
            </div>
            <div>
              <dt>Sigla do órgão</dt>
              <dd>{servidor.sigla_orgao ?? <NaoInformado />}</dd>
            </div>
            <div>
              <dt>UF</dt>
              {servidor.uf === null ? (
                <dd className="ausente">
                  {aposentado
                    ? 'Não informada — o conjunto de aposentados não traz UF'
                    : 'Não informada'}
                </dd>
              ) : (
                <dd>{servidor.uf}</dd>
              )}
            </div>
          </dl>
        </section>

        <section aria-labelledby="sec-carreira">
          <h3 className="subtitulo" id="sec-carreira">
            {aposentado ? 'Aposentadoria' : 'Carreira'}
          </h3>
          <dl className="dados">
            {aposentado ? (
              <>
                <div>
                  <dt>Tipo</dt>
                  <dd>{servidor.tipo_aposentadoria ?? <NaoInformado />}</dd>
                </div>
                <div>
                  <dt>Fundamento legal</dt>
                  <dd>{servidor.fundamento_legal ?? <NaoInformado />}</dd>
                </div>
                <div>
                  <dt>Portaria</dt>
                  <dd>{servidor.portaria ?? <NaoInformado />}</dd>
                </div>
                <div>
                  <dt>Data da aposentadoria</dt>
                  <dd className="num">
                    {servidor.data_aposentadoria === null ? (
                      <NaoInformado />
                    ) : (
                      formatDate(servidor.data_aposentadoria)
                    )}
                  </dd>
                </div>
              </>
            ) : (
              <div>
                <dt>Código da carreira</dt>
                <dd>{servidor.codigo_carreira ?? <NaoInformado />}</dd>
              </div>
            )}
            <div>
              <dt>Ingresso no serviço público</dt>
              <dd>
                <span className="num">
                  {servidor.data_ingresso === null ? <NaoInformado /> : formatDate(servidor.data_ingresso)}
                </span>
                {servidor.forma_ingresso !== null && ` · ${servidor.forma_ingresso}`}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </section>
  )
}
