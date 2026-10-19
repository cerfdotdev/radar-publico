import React, { useState, useEffect } from 'react'
import './App.css'
import type { Servidor, Meta, ServidoresResponse, ApiErrorResponse } from './types'
import { formatCurrency } from './utils'

export function App() {
  const [nome, setNome] = useState(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('nome') || ''
    }
    return ''
  })
  const [buscaAtiva, setBuscaAtiva] = useState('')
  const [erroValidacao, setErroValidacao] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [servidores, setServidores] = useState<Servidor[] | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [erroApi, setErroApi] = useState<string | null>(null)

  async function executarBusca(termo: string, atualizarHistorico = true) {
    const termoLimpo = termo.trim()

    if (!termoLimpo) {
      setErroValidacao('Informe um nome para pesquisar.')
      return
    }

    if (termoLimpo.length < 2) {
      setErroValidacao('O nome deve ter pelo menos 2 caracteres.')
      return
    }

    if (termoLimpo.length > 100) {
      setErroValidacao('O nome deve ter no máximo 100 caracteres.')
      return
    }

    setErroValidacao(null)
    setErroApi(null)
    setLoading(true)
    setBuscaAtiva(termoLimpo)

    if (atualizarHistorico) {
      const url = new URL(window.location.href)
      url.searchParams.set('nome', termoLimpo)
      window.history.pushState({}, '', url.toString())
    }

    try {
      const response = await fetch(`/api/servidores?nome=${encodeURIComponent(termoLimpo)}`)
      if (!response.ok) {
        let msg = `Erro ao consultar a API (HTTP ${response.status})`
        try {
          const errData = (await response.json()) as ApiErrorResponse
          if (errData.error?.message) {
            msg = errData.error.message
          }
        } catch {
          // Mantém mensagem padrão
        }
        setErroApi(msg)
        setServidores([])
        setMeta(null)
        return
      }

      const json = (await response.json()) as ServidoresResponse
      setServidores(json.data || [])
      setMeta(json.meta || null)
    } catch {
      setErroApi('Não foi possível conectar ao servidor. Verifique a conexão com a API.')
      setServidores([])
      setMeta(null)
    } finally {
      setLoading(false)
    }
  }

  // Executa a busca se já houver parâmetro ?nome= na URL ao carregar
  useEffect(() => {
    const nomeParam = new URLSearchParams(window.location.search).get('nome')
    if (nomeParam) {
      void executarBusca(nomeParam, false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void executarBusca(nome)
  }

  return (
    <>
      <header className="topo">
        <div className="container">
          <a className="marca" href="/">
            <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
              <circle cx="14" cy="14" r="12.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="14" cy="14" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.45" />
              <path d="M14 14 L14 1.5 A12.5 12.5 0 0 1 24.8 7.75 Z" fill="var(--primary)" />
              <circle cx="14" cy="14" r="2" fill="currentColor" />
            </svg>
            Radar Público
          </a>
          <nav className="nav" aria-label="Principal">
            <a href="/" aria-current="page">Buscar</a>
            <a href="#sobre">Sobre os dados</a>
            <a href="#api">API</a>
          </nav>
          <button className="menu-celular" type="button" aria-label="Abrir menu" aria-expanded="false">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
        </div>
      </header>

      <main className="container pagina">
        <div>
          <h1 className="titulo-pagina">Buscar servidores federais</h1>
          <p className="lead">
            Consulte vínculos de servidores ativos e aposentados do Poder Executivo Federal, com dados abertos do governo.
          </p>
        </div>

        <search aria-label="Buscar servidores">
          <form className="busca" onSubmit={handleSubmit}>
            <div className={`campo ${erroValidacao ? 'campo--erro' : ''}`}>
              <div className="busca__nome-topo">
                <label className="campo__rotulo" htmlFor="campo-nome">
                  Nome do servidor
                </label>
              </div>
              <div className="busca__linha">
                <input
                  className="controle controle--grande"
                  id="campo-nome"
                  name="nome"
                  type="text"
                  placeholder="Ex.: Maria da Silva"
                  value={nome}
                  onChange={(e) => {
                    setNome(e.target.value)
                    if (erroValidacao) setErroValidacao(null)
                  }}
                  aria-invalid={erroValidacao ? 'true' : 'false'}
                  aria-describedby={erroValidacao ? 'dica-nome-erro' : 'dica-nome'}
                  disabled={loading}
                />
                <button
                  className="btn btn--primario btn--grande"
                  type="submit"
                  disabled={loading}
                  aria-busy={loading}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                    <circle cx="11" cy="11" r="7" />
                    <path d="M20 20l-3.5-3.5" />
                  </svg>
                  {loading ? 'Buscando…' : 'Buscar'}
                </button>
                {erroValidacao ? (
                  <p className="campo__erro" id="dica-nome-erro" role="alert">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                      <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 3.5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 4.5zm0 7a.875.875 0 1 1 0-1.75.875.875 0 0 1 0 1.75z" />
                    </svg>
                    {erroValidacao}
                  </p>
                ) : (
                  <p className="aux" id="dica-nome">
                    Digite o nome completo ou partes do nome (mínimo de 2 caracteres).
                  </p>
                )}
              </div>
            </div>
          </form>
        </search>

        {erroApi && (
          <div className="aviso aviso--erro" role="alert">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <div>
              <strong>Não foi possível carregar os resultados</strong>
              <span>{erroApi}</span>
            </div>
          </div>
        )}

        {loading && (
          <div className="esqueleto" aria-busy="true" aria-label="Carregando resultados">
            <div className="esqueleto__topo" />
            <div className="esqueleto__linha"><i style={{ width: '35%' }} /></div>
            <div className="esqueleto__linha"><i style={{ width: '55%' }} /></div>
            <div className="esqueleto__linha"><i style={{ width: '45%' }} /></div>
          </div>
        )}

        {!loading && servidores !== null && servidores.length === 0 && !erroApi && (
          <section className="estado-vazio" aria-labelledby="vazio-titulo">
            <h2 className="subtitulo" id="vazio-titulo">Nenhum resultado encontrado</h2>
            <p className="aux">
              Não encontramos nenhum servidor com o nome &ldquo;<strong>{buscaAtiva}</strong>&rdquo;. Verifique a ortografia ou tente pesquisar com menos termos.
            </p>
          </section>
        )}

        {!loading && servidores !== null && servidores.length > 0 && (
          <section className="resultados" aria-labelledby="res-titulo">
            <div className="resultados__topo">
              <div>
                <h2 className="titulo-secao" id="res-titulo" aria-live="polite">
                  {meta?.total_exato === false
                    ? `Mais de 10.000 resultados para “${buscaAtiva}”`
                    : `${meta?.total ?? servidores.length} ${
                        (meta?.total ?? servidores.length) === 1 ? 'resultado encontrado' : 'resultados encontrados'
                      } para “${buscaAtiva}”`}
                </h2>
              </div>
            </div>

            {meta && !meta.total_exato && (
              <output className="aviso aviso--atencao">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <div>
                  <strong>Muitos resultados encontrados</strong>
                  <span>Esta busca retornou mais de 10.000 servidores. Refine os termos informando o nome completo.</span>
                </div>
              </output>
            )}

            {/* Tabela para visualização Desktop */}
            <div className="tabela-caixa">
              <table className="tabela">
                <caption className="sr-only">Servidores públicos encontrados</caption>
                <thead>
                  <tr>
                    <th scope="col">Nome</th>
                    <th scope="col">Situação</th>
                    <th scope="col">Cargo</th>
                    <th scope="col">Órgão</th>
                    <th scope="col">UF</th>
                    <th scope="col" className="direita">Valor (R$)</th>
                  </tr>
                </thead>
                <tbody>
                  {servidores.map((servidor) => (
                    <tr key={servidor.id}>
                      <th scope="row">
                        <span className="fonte-dado">{servidor.nome}</span>
                      </th>
                      <td>
                        {servidor.situacao === 'ativo' ? (
                          <span className="pilula pilula--ativo">
                            <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
                              <circle cx="4" cy="4" r="4" fill="currentColor" />
                            </svg>
                            Ativo
                          </span>
                        ) : (
                          <span className="pilula pilula--aposentado">
                            <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
                              <circle cx="4" cy="4" r="3" fill="none" stroke="currentColor" strokeWidth="1.6" />
                            </svg>
                            Aposentado
                          </span>
                        )}
                      </td>
                      <td className="secundario fonte-dado">{servidor.cargo || '—'}</td>
                      <td className="secundario fonte-dado">
                        {servidor.orgao}
                        {servidor.sigla_orgao ? ` (${servidor.sigla_orgao})` : ''}
                      </td>
                      <td className="num secundario">
                        {servidor.uf ? servidor.uf : <span aria-label="não informado">—</span>}
                      </td>
                      <td className="num direita">{formatCurrency(servidor.valor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Lista para visualização Mobile (abaixo de 640px) */}
            <ul className="lista" aria-label="Lista de servidores encontrados">
              {servidores.map((servidor) => (
                <li key={`mobile-${servidor.id}`}>
                  <div className="lista-item">
                    <div className="lista__linha">
                      <strong className="fonte-dado">{servidor.nome}</strong>
                      <span className="num">{formatCurrency(servidor.valor)}</span>
                    </div>
                    <div className="lista__meta">
                      {servidor.situacao === 'ativo' ? (
                        <span className="pilula pilula--ativo">Ativo</span>
                      ) : (
                        <span className="pilula pilula--aposentado">Aposentado</span>
                      )}
                      <span className="secundario">{servidor.uf || 'Brasil'}</span>
                    </div>
                    <div className="aux secundario fonte-dado">
                      {servidor.cargo} · {servidor.sigla_orgao || servidor.orgao}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="nota-fonte">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>
            Dados públicos disponibilizados pelo Portal da Transparência e dados.gov.br. Atualizado conforme a competência mais recente disponível.
          </span>
        </footer>
      </main>
    </>
  )
}

export default App
