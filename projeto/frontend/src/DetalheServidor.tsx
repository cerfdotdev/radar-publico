import { useEffect, useState } from 'react'
import { buscarServidor, type DetailOutcome } from './api'
import { formatCurrency, formatDate, formatReference } from './format'
import { NaoInformado } from './NaoInformado'
import { SituacaoPill } from './SituacaoPill'
import type { Servidor, ServidorDetalhe } from './types'

type EstadoDetalhe = { kind: 'carregando' } | DetailOutcome

/**
 * Resultado único da busca: ficha do vínculo (docs/design/detalhe.html). Cabeçalho e
 * vínculo saem da própria busca, na hora; carreira, aposentadoria e ingresso vêm de
 * GET /api/servidores/<id> e só aparecem quando chegam, para um campo que não carregou
 * nunca parecer "não informado" na fonte.
 */
export function DetalheServidor({ resumo }: { resumo: Servidor }) {
  const [estado, setEstado] = useState<EstadoDetalhe>({ kind: 'carregando' })

  useEffect(() => {
    const controller = new AbortController()
    buscarServidor(resumo.id, controller.signal).then(
      (resultado) => {
        if (!controller.signal.aborted) setEstado(resultado)
      },
      () => {
        // Só rejeita quando cancelada (tela trocada): não há o que mostrar.
      },
    )
    return () => controller.abort()
  }, [resumo.id])

  const aposentado = resumo.situacao === 'aposentado'
  const detalhe = estado.kind === 'ok' ? estado.servidor : null

  return (
    <article className="detalhe" aria-labelledby="detalhe-titulo">
      <div className="cabecalho-vinculo">
        <div className="cabecalho-vinculo__id">
          <SituacaoPill situacao={resumo.situacao} />
          <h3 className="titulo-pagina fonte-dado" id="detalhe-titulo">
            {resumo.nome}
          </h3>
          <p className="fonte-dado detalhe__resumo">
            {resumo.cargo ?? 'Cargo não informado'} · {resumo.orgao}
            {resumo.sigla_orgao === null ? '' : ` (${resumo.sigla_orgao})`}
          </p>
        </div>
        <div className="cabecalho-vinculo__valor">
          <span className="aux">{aposentado ? 'Valor da aposentadoria' : 'Remuneração'}</span>
          <span className="valor-grande">
            {resumo.valor === null ? <NaoInformado /> : `R$ ${formatCurrency(resumo.valor)}`}
          </span>
          {detalhe !== null && detalhe.referencia !== null && (
            <span className="aux">Referência {formatReference(detalhe.referencia)}</span>
          )}
        </div>
      </div>

      <div className="colunas">
        <section aria-labelledby="sec-vinculo">
          <h4 className="subtitulo" id="sec-vinculo">
            Vínculo
          </h4>
          <dl className="dados">
            <div>
              <dt>Cargo</dt>
              <dd>{resumo.cargo ?? <NaoInformado />}</dd>
            </div>
            <div>
              <dt>Órgão</dt>
              <dd>{resumo.orgao}</dd>
            </div>
            <div>
              <dt>Sigla do órgão</dt>
              <dd>{resumo.sigla_orgao ?? <NaoInformado />}</dd>
            </div>
            <div>
              <dt>UF</dt>
              {resumo.uf === null ? (
                <dd className="ausente">
                  {aposentado ? 'Não informada — o conjunto de aposentados não traz UF' : 'Não informada'}
                </dd>
              ) : (
                <dd>{resumo.uf}</dd>
              )}
            </div>
          </dl>
        </section>

        <section aria-labelledby="sec-carreira" aria-busy={estado.kind === 'carregando'}>
          <h4 className="subtitulo" id="sec-carreira">
            {aposentado ? 'Aposentadoria' : 'Carreira'}
          </h4>
          {estado.kind === 'carregando' && <p className="aux">Carregando a ficha completa…</p>}
          {estado.kind === 'error' && (
            <div className="aviso aviso--atencao">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M12 3l9 16H3z" />
                <path d="M12 10v4M12 17h.01" />
              </svg>
              <div>
                <strong>Não foi possível carregar a ficha completa</strong>
                <span>
                  {aposentado ? 'Os dados da aposentadoria' : 'Os dados da carreira'} e do ingresso não vieram da API.
                  Cargo, órgão, UF e valor acima são os da busca.
                </span>
              </div>
            </div>
          )}
          {detalhe !== null && <DadosDoVinculo detalhe={detalhe} aposentado={aposentado} />}
        </section>
      </div>
    </article>
  )
}

function DadosDoVinculo({ detalhe, aposentado }: { detalhe: ServidorDetalhe; aposentado: boolean }) {
  return (
    <dl className="dados">
      {aposentado ? (
        <>
          <div>
            <dt>Tipo</dt>
            <dd>{detalhe.tipo_aposentadoria ?? <NaoInformado />}</dd>
          </div>
          <div>
            <dt>Fundamento legal</dt>
            <dd>{detalhe.fundamento_legal ?? <NaoInformado />}</dd>
          </div>
          <div>
            <dt>Portaria</dt>
            <dd>{detalhe.portaria ?? <NaoInformado />}</dd>
          </div>
          <div>
            <dt>Data da aposentadoria</dt>
            <dd className="num">
              {detalhe.data_aposentadoria === null ? <NaoInformado /> : formatDate(detalhe.data_aposentadoria)}
            </dd>
          </div>
        </>
      ) : (
        <div>
          <dt>Código da carreira</dt>
          <dd>{detalhe.codigo_carreira ?? <NaoInformado />}</dd>
        </div>
      )}
      <div>
        <dt>Ingresso no serviço público</dt>
        <dd>
          <span className="num">
            {detalhe.data_ingresso === null ? <NaoInformado /> : formatDate(detalhe.data_ingresso)}
          </span>
          {detalhe.forma_ingresso !== null && ` · ${detalhe.forma_ingresso}`}
        </dd>
      </div>
    </dl>
  )
}
