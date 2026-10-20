import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { SEARCH_TIMEOUT_MS } from './api'
import {
  corpoDetalhe,
  corpoServidores,
  erroApi,
  fetchPendente,
  fetchRespondendo,
  respostaJson,
  respostaTexto,
  SERVIDOR_APOSENTADO,
  SERVIDOR_ATIVO,
} from './testUtils'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

const campoNome = () => screen.getByRole('textbox', { name: 'Nome do servidor' })
const botaoBuscar = () => screen.getByRole('button', { name: /^(Buscar|Buscando…)$/ })
const regiaoViva = () => screen.getByRole('status')
const campoLimite = () => screen.getByRole('spinbutton', { name: /^Até/ })
const campoCargo = () => screen.getByRole('textbox', { name: 'Cargo' })
const campoOrgao = () => screen.getByRole('textbox', { name: 'Órgão' })
const campoUf = () => screen.getByRole('combobox', { name: /^UF/ })
const botaoModo = (nome: 'Nome exato' | 'Nome parecido') => screen.getByRole('button', { name: nome })
const tituloResultados = () => screen.getByRole('heading', { level: 2 })

// URL do último fetch do mock global.
const fetchMockUrl = () => String(vi.mocked(fetch).mock.lastCall?.[0])

function abrirCom(url: string, arvore = <App />) {
  window.history.replaceState(null, '', url)
  return render(arvore)
}

function digitarEBuscar(nome: string) {
  fireEvent.change(campoNome(), { target: { value: nome } })
  fireEvent.click(botaoBuscar())
}

// O navegador troca a URL e dispara popstate ao voltar ou avançar.
function navegarPara(url: string) {
  act(() => {
    window.history.pushState(null, '', url)
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
}

describe('Tela de busca (issue #11)', () => {
  it('mostra topo, título e formulário, sem controles que não fazem nada', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'Buscar servidores federais' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Radar Público' })).toHaveAttribute('href', '/')
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['Buscar'])
    expect(screen.queryByRole('button', { name: 'Abrir menu' })).not.toBeInTheDocument()
    expect(document.querySelector('search')).toContainElement(campoNome())
    expect(campoNome()).toHaveAccessibleDescription('Digite o nome completo, como no registro.')
    expect(regiaoViva()).toBeEmptyDOMElement()
  })

  it('valida o nome no próprio campo, sem chamar a API', () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    render(<App />)

    fireEvent.click(botaoBuscar())
    expect(campoNome()).toHaveAttribute('aria-invalid', 'true')
    expect(campoNome()).toHaveAccessibleDescription('Informe um nome ou pelo menos um filtro: cargo, órgão ou UF.')
    expect(screen.getByRole('alert')).toHaveTextContent('Informe um nome ou pelo menos um filtro: cargo, órgão ou UF.')
    expect(campoNome()).toHaveFocus()

    // Editar o campo tira o erro.
    fireEvent.change(campoNome(), { target: { value: 'Maria1' } })
    expect(campoNome()).toHaveAttribute('aria-invalid', 'false')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    fireEvent.click(botaoBuscar())
    expect(campoNome()).toHaveAccessibleDescription("Use só letras, espaços, apóstrofo ('), ponto (.) e hífen (-).")

    digitarEBuscar('A')
    expect(screen.getByRole('alert')).toHaveTextContent('O nome deve ter pelo menos 2 caracteres.')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(window.location.search).toBe('')
  })

  it('busca mantendo o foco no campo, ignora envios durante o carregamento e mostra tabela e lista', async () => {
    const { fetchMock, pedidos } = fetchPendente()
    render(<App />)
    const campo = campoNome()
    fireEvent.change(campo, { target: { value: '  Maria   da Silva ' } })
    campo.focus()
    fireEvent.submit(campo.closest('form') as HTMLFormElement)

    expect(pedidos[0].url).toBe('/api/servidores?nome=Maria+da+Silva')
    expect(window.location.search).toBe('?nome=Maria+da+Silva')

    // Carregando: anunciado, botão focável e ocupado, campo só leitura e ainda com o foco.
    expect(regiaoViva()).toHaveTextContent('Buscando…')
    expect(botaoBuscar()).toHaveTextContent('Buscando…')
    expect(botaoBuscar()).toHaveAttribute('aria-busy', 'true')
    expect(botaoBuscar()).toHaveAttribute('aria-disabled', 'true')
    expect(botaoBuscar()).toBeEnabled()
    expect(campo).toBeEnabled()
    expect(campo).toHaveAttribute('readonly')
    expect(campo).toHaveFocus()

    fireEvent.click(botaoBuscar())
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => pedidos[0].responder(respostaJson(200, corpoServidores())))

    expect(tituloResultados()).toHaveTextContent('2 resultados encontrados para “Maria da Silva”')
    expect(tituloResultados()).not.toHaveAttribute('aria-live')
    expect(regiaoViva()).toHaveTextContent('2 resultados encontrados para “Maria da Silva”.')
    expect(campo).toHaveFocus()
    expect(campo).not.toHaveAttribute('readonly')
    expect(campo).toHaveValue('Maria da Silva')
    expect(botaoBuscar()).toHaveAttribute('aria-disabled', 'false')

    const linhas = within(screen.getByRole('table')).getAllByRole('row')
    expect(linhas).toHaveLength(3)
    expect(within(linhas[1]).getByRole('rowheader')).toHaveTextContent('MARIA DA SILVA')
    expect(linhas[1]).toHaveTextContent('Ativo')
    expect(linhas[1]).toHaveTextContent('CONTROLADORIA-GERAL DA UNIAO')
    expect(linhas[1]).toHaveTextContent('19.090,67')
    expect(linhas[2]).toHaveTextContent('Aposentado')
    expect(linhas[2]).toHaveTextContent('MINISTERIO DA AGRICULTURA E PECUARIA (MAPA)')
    expect(linhas[2]).toHaveTextContent('7.006,78')
    // Cargo e UF null: travessão com "não informado" para leitores de tela.
    expect(within(linhas[2]).getAllByText('não informado')).toHaveLength(2)
  })

  it('lista do celular: UF ausente como "não informado", sem separador solto, com R$ e marcadores', async () => {
    fetchRespondendo(() => respostaJson(200, corpoServidores()))
    abrirCom('/?nome=Maria')
    const lista = await screen.findByRole('list', { name: 'Servidores encontrados' })
    const [ativo, aposentado] = within(lista).getAllByRole('listitem')

    expect(ativo).toHaveTextContent(/R\$\s19\.090,67/)
    expect(ativo).toHaveTextContent('ANALISTA DE FINANCAS E CONTROLE · CONTROLADORIA-GERAL DA UNIAO')
    expect(ativo).toHaveTextContent('UF DF')

    expect(aposentado).toHaveTextContent(/R\$\s7\.006,78/)
    expect(aposentado).toHaveTextContent('MAPA')
    expect(aposentado.textContent).not.toContain('·')
    expect(within(aposentado).getByText('não informado')).toBeInTheDocument()
    expect(aposentado).not.toHaveTextContent('Brasil')

    // Marcador cheio para ativo e vazado para aposentado: a situação nunca depende só da cor.
    expect(within(ativo).getByText('Ativo').querySelector('circle')).toHaveAttribute('fill', 'currentColor')
    expect(within(aposentado).getByText('Aposentado').querySelector('circle')).toHaveAttribute('fill', 'none')
  })

  it('total_exato false: "mais de 10.000", aviso para refinar e quantos estão na tela', async () => {
    fetchRespondendo(() =>
      respostaJson(200, corpoServidores(undefined, { total: 10000, total_exato: false, total_pages: 500 })),
    )
    abrirCom('/?nome=Maria')
    expect(await screen.findByText('Refine a busca')).toBeInTheDocument()
    expect(tituloResultados()).toHaveTextContent('Mais de 10.000 resultados para “Maria”')
    expect(
      within(screen.getByRole('navigation', { name: 'Paginação' })).getByText(/Mostrando 1–2 de 10\.000/),
    ).toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('Mais de 10.000 resultados para “Maria”. Mostrando os 2 primeiros.')
  })

  it('total maior que a página: mostra o total exato e quantos estão na tela', async () => {
    fetchRespondendo(() => respostaJson(200, corpoServidores(undefined, { total: 2345, total_pages: 118 })))
    abrirCom('/?nome=Maria')
    const paginacao = await screen.findByRole('navigation', { name: 'Paginação' })
    expect(paginacao).toHaveTextContent('Mostrando 1–2 de 2.345 · página 1 de 118')
    expect(regiaoViva()).toHaveTextContent('Mostrando os 2 primeiros.')
    expect(tituloResultados()).toHaveTextContent('2.345 resultados encontrados para “Maria”')
    expect(screen.queryByText('Refine a busca')).not.toBeInTheDocument()
  })

  it('resultado único mostra o detalhe do vínculo, sem tabela', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        String(input).startsWith('/api/servidores/')
          ? respostaJson(200, corpoDetalhe())
          : respostaJson(200, corpoServidores([SERVIDOR_ATIVO])),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    abrirCom('/?nome=Maria')

    // Um só h1 na página: o nome fica abaixo do título dos resultados (h2) e as seções em h4.
    expect(await screen.findByRole('heading', { level: 3, name: 'MARIA DA SILVA' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 4, name: 'Carreira' })).toBeInTheDocument()
    expect(await screen.findByText('301005')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/servidores/1048213', expect.anything())
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText('01/03/2010')).toBeInTheDocument()
    expect(screen.getByText('Referência 05/2026')).toBeInTheDocument()
    expect(screen.getByText(/CONCURSO PUBLICO/)).toBeInTheDocument()
    expect(screen.queryByText('Não foi possível carregar a ficha completa')).not.toBeInTheDocument()
  })

  it('vários resultados: página seguinte muda a URL e busca de novo', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria')
    await act(async () =>
      pedidos[0].responder(
        respostaJson(200, corpoServidores(undefined, { total: 45, total_pages: 3 })),
      ),
    )

    // Na primeira página, "anterior" fica desativado e não aponta para a página 0.
    expect(screen.getByRole('link', { name: 'Página anterior' })).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByRole('link', { name: 'Página anterior' })).toHaveAttribute('href', '/?nome=Maria')

    fireEvent.click(screen.getByRole('link', { name: 'Próxima página' }))
    expect(pedidos[1].url).toBe('/api/servidores?nome=Maria&page=2')
    expect(window.location.search).toBe('?nome=Maria&page=2')

    await act(async () =>
      pedidos[1].responder(
        respostaJson(200, corpoServidores(undefined, { total: 45, total_pages: 3, page: 2 })),
      ),
    )
    expect(screen.getByRole('link', { name: '2' })).toHaveAttribute('aria-current', 'page')
    expect(
      within(screen.getByRole('navigation', { name: 'Paginação' })).getByText(/Mostrando 21–22 de 45/),
    ).toBeInTheDocument()
    // O link clicado sumiu no carregamento: o foco vai para o título dos resultados.
    expect(tituloResultados()).toHaveFocus()
    expect(regiaoViva()).toHaveTextContent('45 resultados encontrados para “Maria”. Mostrando 21–22 de 45.')

    // Celular: Anterior e Próxima, com links de verdade.
    expect(screen.getByRole('link', { name: 'Anterior' })).toHaveAttribute('href', '/?nome=Maria')
    expect(screen.getByRole('link', { name: 'Próxima' })).toHaveAttribute('href', '/?nome=Maria&page=3')

    // Uma busca nova pelo formulário volta a deixar o foco no campo.
    fireEvent.change(campoNome(), { target: { value: 'Joana' } })
    campoNome().focus()
    fireEvent.click(botaoBuscar())
    await act(async () => pedidos[2].responder(respostaJson(200, corpoServidores(undefined, { total: 45, total_pages: 3 }))))
    expect(campoNome()).toHaveFocus()
  })

  it('trocar itens por página volta para a primeira página', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria&page=2')
    await act(async () =>
      pedidos[0].responder(
        respostaJson(200, corpoServidores(undefined, { total: 45, total_pages: 3, page: 2 })),
      ),
    )

    fireEvent.change(screen.getByLabelText('Resultados por página'), { target: { value: '50' } })
    expect(pedidos[1].url).toBe('/api/servidores?nome=Maria&per_page=50')
    expect(window.location.search).toBe('?nome=Maria&per_page=50')
  })

  it('404 NAO_ENCONTRADO mostra o estado vazio, não um erro', async () => {
    fetchRespondendo(() => erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado com os critérios informados.'))
    render(<App />)
    digitarEBuscar('João da Silva Xavier')

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Nenhum vínculo com o nome “João da Silva Xavier”' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/só encontra o nome completo, escrito como no registro/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('Nenhum vínculo com o nome “João da Silva Xavier”.')
  })

  it.each([
    ['falha de rede', () => Promise.reject(new TypeError('Failed to fetch')), 'Não foi possível conectar à API'],
    [
      '200 que não é JSON',
      () => Promise.resolve(respostaTexto(200, '<!doctype html><html></html>')),
      'A API respondeu, mas não em JSON',
    ],
    [
      '200 com data que não é lista',
      () => Promise.resolve(respostaJson(200, { data: 'oops', meta: null })),
      'Resposta inesperada da API',
    ],
    [
      '200 com item sem valor',
      () => Promise.resolve(respostaJson(200, corpoServidores([{ ...SERVIDOR_ATIVO, valor: undefined as unknown as number }]))),
      'Resposta inesperada da API',
    ],
    ['502 em HTML', () => Promise.resolve(respostaTexto(502, '<html>Bad Gateway</html>')), 'A API está fora do ar'],
    [
      '504 do nginx',
      () => Promise.resolve(erroApi(504, 'TEMPO_ESGOTADO', 'A API demorou demais para responder.')),
      'A busca demorou demais e foi interrompida',
    ],
  ])('%s mostra um aviso de erro, sem tela branca', async (_caso, responder, titulo) => {
    vi.stubGlobal('fetch', vi.fn(responder))
    abrirCom('/?nome=Maria')
    expect(await screen.findByRole('alert')).toHaveTextContent(titulo)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('NaN')
  })

  it('400 da API aparece no campo, com o foco nele', async () => {
    fetchRespondendo(() => erroApi(400, 'PARAMETRO_INVALIDO', "'nome' contém caracteres não permitidos."))
    render(<App />)
    digitarEBuscar('Maria')

    expect(await screen.findByRole('alert')).toHaveTextContent("'nome' contém caracteres não permitidos.")
    expect(campoNome()).toHaveAttribute('aria-invalid', 'true')
    expect(campoNome()).toHaveAccessibleDescription("'nome' contém caracteres não permitidos.")
    expect(campoNome()).toHaveFocus()
  })

  it('429 mostra aviso informativo com os segundos do Retry-After', async () => {
    fetchRespondendo(() => erroApi(429, 'MUITAS_REQUISICOES', 'Muitas requisições.', { 'Retry-After': '12' }))
    abrirCom('/?nome=Maria')
    expect(await screen.findByText('Muitas buscas em pouco tempo')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('Você pode buscar de novo em 12 segundos.')
  })
})

describe('Nome parecido e filtros combinados (issue #20)', () => {
  it('combina nome exato, cargo, órgão e UF numa requisição só e guarda tudo na URL', async () => {
    const { pedidos } = fetchPendente()
    render(<App />)
    fireEvent.change(campoNome(), { target: { value: 'Maria' } })
    fireEvent.change(campoCargo(), { target: { value: ' professor ' } })
    fireEvent.change(campoOrgao(), { target: { value: 'INSS' } })
    fireEvent.change(campoUf(), { target: { value: 'RJ' } })
    fireEvent.click(botaoBuscar())

    expect(pedidos).toHaveLength(1)
    expect(pedidos[0].url).toBe('/api/servidores?nome=Maria&cargo=professor&orgao=INSS&uf=RJ')
    expect(window.location.search).toBe('?nome=Maria&cargo=professor&orgao=INSS&uf=RJ')

    await act(async () => pedidos[0].responder(respostaJson(200, corpoServidores([SERVIDOR_ATIVO]))))
    expect(tituloResultados()).toHaveTextContent('1 resultado encontrado para “Maria”, cargo “professor”, órgão “INSS” em RJ')
  })

  it('busca só por filtros, sem nome, e descreve os filtros no título e no vazio', async () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    abrirCom('/?cargo=professor&uf=RJ')
    expect(campoCargo()).toHaveValue('professor')
    expect(campoUf()).toHaveValue('RJ')
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent(
      '2 resultados encontrados para cargo “professor” em RJ',
    )
    expect(fetchMock).toHaveBeenCalledWith('/api/servidores?cargo=professor&uf=RJ', expect.anything())

    fetchRespondendo(() => erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado com esses filtros.'))
    navegarPara('/?orgao=INSS&uf=AC')
    expect(
      await screen.findByRole('heading', { level: 2, name: 'Nenhum vínculo encontrado para órgão “INSS” em AC' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Nenhum vínculo atende a todos os filtros/)).toBeInTheDocument()
  })

  it('nome parecido envia similar e limit com cargo, órgão e UF, e mostra a semelhança', async () => {
    const { pedidos } = fetchPendente()
    render(<App />)
    fireEvent.change(campoCargo(), { target: { value: 'professor' } })
    fireEvent.change(campoNome(), { target: { value: '%maria%silva%' } })
    fireEvent.click(botaoModo('Nome parecido'))

    expect(botaoModo('Nome parecido')).toHaveAttribute('aria-pressed', 'true')
    expect(campoNome()).toHaveValue('%maria%silva%')
    expect(campoNome()).toHaveAccessibleDescription(/Use % no lugar das partes que você não sabe/)
    expect(campoLimite()).toHaveValue(100)
    // A API combina os filtros com similar: continuam ativos, com o que já estava digitado.
    expect(campoCargo()).toBeEnabled()
    expect(campoCargo()).toHaveValue('professor')
    expect(screen.getByRole('group', { name: 'Filtros' })).not.toHaveAttribute('aria-describedby')
    expect(screen.queryByText(/usa só o nome/)).not.toBeInTheDocument()

    fireEvent.change(campoOrgao(), { target: { value: 'INSS' } })
    fireEvent.change(campoUf(), { target: { value: 'RJ' } })
    fireEvent.change(campoLimite(), { target: { value: '50' } })
    fireEvent.click(botaoBuscar())
    expect(pedidos[0].url).toBe('/api/servidores?similar=%25maria%25silva%25&limit=50&cargo=professor&orgao=INSS&uf=RJ')
    expect(window.location.search).toBe('?similar=%25maria%25silva%25&limit=50&cargo=professor&orgao=INSS&uf=RJ')

    const corpo = corpoServidores(
      [
        { ...SERVIDOR_ATIVO, similaridade: 0.857 },
        { ...SERVIDOR_APOSENTADO, id: 2, similaridade: 0.5 },
      ],
      { per_page: 50 },
    )
    await act(async () => pedidos[0].responder(respostaJson(200, corpo)))

    expect(tituloResultados()).toHaveTextContent(
      'Os 2 nomes mais parecidos com “%maria%silva%”, cargo “professor”, órgão “INSS” em RJ',
    )
    expect(regiaoViva()).toHaveTextContent(
      'Os 2 nomes mais parecidos com “%maria%silva%”, cargo “professor”, órgão “INSS” em RJ.',
    )
    const tabela = screen.getByRole('table')
    expect(within(tabela).getByRole('columnheader', { name: 'Semelhança' })).toHaveAttribute('aria-sort', 'descending')
    expect(within(tabela).getAllByRole('row')[1]).toHaveTextContent('0,86')
    expect(within(screen.getByRole('list', { name: 'Servidores encontrados' })).getAllByRole('listitem')[1]).toHaveTextContent(
      'semelhança 0,50',
    )

    // Voltar ao nome exato mantém os filtros digitados.
    fireEvent.click(botaoModo('Nome exato'))
    expect(campoCargo()).toHaveValue('professor')
    expect(campoUf()).toHaveValue('RJ')
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
  })

  it('valida o padrão parecido e o limite no próprio campo, sem chamar a API', () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    render(<App />)
    fireEvent.click(botaoModo('Nome parecido'))

    digitarEBuscar('%AB%')
    expect(campoNome()).toHaveAccessibleDescription('Digite pelo menos 3 letras além dos %.')
    expect(campoNome()).toHaveFocus()

    fireEvent.change(campoNome(), { target: { value: '%MARIA%' } })
    fireEvent.change(campoLimite(), { target: { value: '101' } })
    fireEvent.click(botaoBuscar())
    expect(campoLimite()).toHaveAttribute('aria-invalid', 'true')
    expect(campoLimite()).toHaveAccessibleDescription('O limite deve ser um número inteiro de 1 a 100.')
    expect(campoLimite()).toHaveFocus()
    expect(campoNome()).toHaveAttribute('aria-invalid', 'false')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(window.location.search).toBe('')
  })

  it('cargo sem correspondente (404 CARGO_NAO_ENCONTRADO) aparece no campo cargo, com o foco nele', async () => {
    fetchRespondendo(() => erroApi(404, 'CARGO_NAO_ENCONTRADO', 'Nenhum cargo corresponde à busca.'))
    abrirCom('/?nome=Maria&cargo=pofessor')

    expect(await screen.findByRole('alert')).toHaveTextContent('Nenhum cargo contém “pofessor”.')
    expect(campoCargo()).toHaveAttribute('aria-invalid', 'true')
    expect(campoCargo()).toHaveAccessibleDescription(/^Nenhum cargo contém “pofessor”/)
    expect(campoCargo()).toHaveFocus()
    expect(campoNome()).toHaveAttribute('aria-invalid', 'false')
    expect(screen.queryByText('Não foi possível concluir a busca')).not.toBeInTheDocument()
    // No celular, a seção recolhida abre sozinha para mostrar o erro.
    expect(screen.getByRole('button', { name: /^Filtros/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('botão Filtros do celular conta os filtros preenchidos e abre a seção', () => {
    fetchPendente()
    abrirCom('/?cargo=professor&uf=RJ')
    const botao = screen.getByRole('button', { name: 'Filtros, 2 preenchidos' })
    expect(botao).toHaveAttribute('aria-expanded', 'false')
    expect(botao).toHaveAttribute('aria-controls', 'filtros')
    expect(document.getElementById('filtros')).toBe(screen.getByRole('group', { name: 'Filtros' }))
    fireEvent.click(botao)
    expect(botao).toHaveAttribute('aria-expanded', 'true')
  })

  it('UF fica habilitada durante a busca, para o foco não se perder', () => {
    fetchPendente()
    abrirCom('/?uf=RJ')
    expect(regiaoViva()).toHaveTextContent('Buscando…')
    expect(campoUf()).toBeEnabled()
    expect(campoCargo()).toHaveAttribute('readonly')
  })

  it('a URL define o modo; navegar no histórico restaura modo, limite e filtros', async () => {
    fetchRespondendo(() => respostaJson(200, corpoServidores()))
    abrirCom('/?nome=Maria&uf=RJ')
    expect(botaoModo('Nome exato')).toHaveAttribute('aria-pressed', 'true')
    expect(campoUf()).toHaveValue('RJ')

    navegarPara('/?similar=%25MARIA%25&limit=20')
    expect(botaoModo('Nome parecido')).toHaveAttribute('aria-pressed', 'true')
    expect(campoNome()).toHaveValue('%MARIA%')
    expect(campoLimite()).toHaveValue(20)
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('Os 2 nomes mais parecidos com “%MARIA%”')

    navegarPara('/?nome=Maria&uf=RJ')
    expect(botaoModo('Nome exato')).toHaveAttribute('aria-pressed', 'true')
    expect(campoNome()).toHaveValue('Maria')
    expect(campoUf()).toHaveValue('RJ')
  })
})

describe('Paginação, detalhe e estados (issue #21)', () => {
  it('detalhe que não carrega: avisa, sem inventar campos "não informados"', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria')
    await act(async () => pedidos[0].responder(respostaJson(200, corpoServidores([SERVIDOR_APOSENTADO]))))

    // Cabeçalho e vínculo saem da busca, na hora; o resto espera o detalhe.
    expect(screen.getByRole('heading', { level: 3, name: 'MARIA DA SILVA' })).toBeInTheDocument()
    expect(screen.getByText('MINISTERIO DA AGRICULTURA E PECUARIA')).toBeInTheDocument()
    expect(screen.getByText('Carregando a ficha completa…')).toBeInTheDocument()
    expect(pedidos[1].url).toBe('/api/servidores/1503377')

    await act(async () => pedidos[1].responder(erroApi(404, 'ROTA_INEXISTENTE', 'Rota não encontrada.')))
    expect(screen.getByText('Não foi possível carregar a ficha completa')).toBeInTheDocument()
    expect(screen.queryByText('Carregando a ficha completa…')).not.toBeInTheDocument()
    expect(screen.queryByText('Tipo')).not.toBeInTheDocument()
    expect(screen.queryByText('Data da aposentadoria')).not.toBeInTheDocument()
    expect(screen.queryByText(/^Referência/)).not.toBeInTheDocument()
    // A falha do detalhe não vira erro da busca.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(tituloResultados()).toHaveTextContent('1 resultado encontrado para “Maria”')
  })

  it('404 PAGINA_INEXISTENTE: estado próprio com link para a última página', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria&page=40')
    expect(pedidos[0].url).toBe('/api/servidores?nome=Maria&page=40')
    await act(async () =>
      pedidos[0].responder(
        erroApi(404, 'PAGINA_INEXISTENTE', 'A página 40 não existe; esta busca tem 3 página(s).'),
      ),
    )

    expect(screen.getByRole('heading', { level: 2, name: 'A página 40 não existe nesta busca' })).toBeInTheDocument()
    expect(screen.getByText(/Esta busca tem 3 páginas\./)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('A página 40 não existe nesta busca.')
    const link = screen.getByRole('link', { name: 'Ir para a página 3' })
    expect(link).toHaveAttribute('href', '/?nome=Maria&page=3')

    fireEvent.click(link)
    expect(pedidos[1].url).toBe('/api/servidores?nome=Maria&page=3')
    expect(window.location.search).toBe('?nome=Maria&page=3')
    await act(async () =>
      pedidos[1].responder(respostaJson(200, corpoServidores(undefined, { total: 42, total_pages: 3, page: 3 }))),
    )
    expect(tituloResultados()).toHaveFocus()
  })

  it('PAGINA_INEXISTENTE sem o total na mensagem leva à primeira página', async () => {
    fetchRespondendo(() => erroApi(404, 'PAGINA_INEXISTENTE', 'Página inexistente.'))
    abrirCom('/?cargo=professor&page=9')
    expect(await screen.findByRole('link', { name: 'Ir para a primeira página' })).toHaveAttribute(
      'href',
      '/?cargo=professor',
    )
  })

  it('página e itens por página fora da faixa na URL valem o padrão', () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria&page=0&per_page=500')
    expect(pedidos[0].url).toBe('/api/servidores?nome=Maria')
  })

  it('busca parecida não pagina: sem seletor por página e sem paginação, nem page na API', async () => {
    fetchRespondendo(() =>
      respostaJson(
        200,
        corpoServidores(
          [
            { ...SERVIDOR_ATIVO, similaridade: 1 },
            { ...SERVIDOR_APOSENTADO, similaridade: 0.8 },
          ],
          { per_page: 100 },
        ),
      ),
    )
    abrirCom('/?similar=%25MARIA%25&limit=100&uf=RJ&page=2&per_page=50')
    expect(await screen.findByRole('table')).toBeInTheDocument()
    // A API recusa page e per_page com similar; o filtro de UF vai junto.
    expect(fetchMockUrl()).toBe('/api/servidores?similar=%25MARIA%25&limit=100&uf=RJ')
    expect(screen.queryByRole('navigation', { name: 'Paginação' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Resultados por página')).not.toBeInTheDocument()
  })

  it('504 explica a causa provável e "Tentar de novo" refaz a busca sem empilhar histórico', async () => {
    const fetchMock = fetchRespondendo(() => erroApi(504, 'TEMPO_ESGOTADO', 'A busca passou do tempo limite.'))
    abrirCom('/?nome=Maria')
    expect(await screen.findByRole('alert')).toHaveTextContent('Acrescente outra parte do nome ou outro filtro')
    const inicio = window.history.length

    fireEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock).toHaveBeenLastCalledWith('/api/servidores?nome=Maria', expect.anything())
    expect(window.history.length).toBe(inicio)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('429 não oferece "Tentar de novo" na hora: o aviso diz quando buscar', async () => {
    fetchRespondendo(() => erroApi(429, 'MUITAS_REQUISICOES', 'Muitas requisições.', { 'Retry-After': '3' }))
    abrirCom('/?nome=Maria')
    expect(await screen.findByText('Muitas buscas em pouco tempo')).toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('Você pode buscar de novo em 3 segundos.')
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).not.toBeInTheDocument()
  })

  it('nome exato sem resultado oferece a busca parecida já montada', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Jo%C3%A3o+da+Silva+Xavier')
    await act(async () => pedidos[0].responder(erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado.')))

    const link = screen.getByRole('link', { name: 'Buscar nomes parecidos: %JOAO%SILVA%XAVIER%' })
    expect(link).toHaveAttribute('href', '/?similar=%25JOAO%25SILVA%25XAVIER%25&limit=100')
    fireEvent.click(link)
    expect(pedidos[1].url).toBe('/api/servidores?similar=%25JOAO%25SILVA%25XAVIER%25&limit=100')
    expect(botaoModo('Nome parecido')).toHaveAttribute('aria-pressed', 'true')
    expect(campoNome()).toHaveValue('%JOAO%SILVA%XAVIER%')
  })

  it('sem resultado com filtros, sugere a busca parecida com os mesmos filtros', async () => {
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria+Silva&uf=RJ&per_page=50')
    await act(async () => pedidos[0].responder(erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado.')))
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Nenhum vínculo encontrado')

    const link = screen.getByRole('link', { name: 'Buscar nomes parecidos: %MARIA%SILVA%' })
    expect(link).toHaveAttribute('href', '/?similar=%25MARIA%25SILVA%25&limit=100&uf=RJ')
    fireEvent.click(link)
    expect(pedidos[1].url).toBe('/api/servidores?similar=%25MARIA%25SILVA%25&limit=100&uf=RJ')
    await act(async () => pedidos[1].responder(erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado.')))
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Nenhum nome parecido com “%MARIA%SILVA%” em RJ')
    expect(screen.getByText(/Com filtros, o nome também precisa atender a todos eles/)).toBeInTheDocument()
  })
})

describe('Busca na URL e no histórico', () => {
  it('com ?nome= na URL, busca ao abrir e preenche o campo', async () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    abrirCom('/?nome=Maria+da+Silva')
    expect(campoNome()).toHaveValue('Maria da Silva')
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('para “Maria da Silva”')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('nome inválido na URL aparece no campo, sem chamar a API', () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    abrirCom('/?nome=a')
    expect(screen.getByRole('alert')).toHaveTextContent('O nome deve ter pelo menos 2 caracteres.')
    expect(campoNome()).toHaveAttribute('aria-invalid', 'true')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('voltar restaura a busca anterior; repetir a mesma busca não duplica o histórico', async () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    render(<App />)
    const inicio = window.history.length

    digitarEBuscar('Maria')
    expect(await screen.findByRole('heading', { level: 2, name: /“Maria”/ })).toBeInTheDocument()
    digitarEBuscar('Joana')
    expect(await screen.findByRole('heading', { level: 2, name: /“Joana”/ })).toBeInTheDocument()
    expect(window.history.length).toBe(inicio + 2)

    digitarEBuscar('Joana')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(await screen.findByRole('heading', { level: 2, name: /“Joana”/ })).toBeInTheDocument()
    expect(window.history.length).toBe(inicio + 2)

    window.history.back()
    await waitFor(() => expect(window.location.search).toBe('?nome=Maria'))
    expect(campoNome()).toHaveValue('Maria')
    expect(await screen.findByRole('heading', { level: 2, name: /“Maria”/ })).toBeInTheDocument()

    window.history.back()
    await waitFor(() => expect(window.location.search).toBe(''))
    await waitFor(() => expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument())
    expect(campoNome()).toHaveValue('')
  })

  it('trocar de busca no meio do carregamento cancela a anterior e ignora a resposta atrasada', async () => {
    let responderPrimeira: (response: Response) => void = () => {}
    const fetchMock = vi
      .fn()
      // A primeira já foi respondida pelo servidor e não reage ao cancelamento.
      .mockImplementationOnce(() => new Promise<Response>((resolve) => (responderPrimeira = resolve)))
      .mockImplementation(() => Promise.resolve(respostaJson(200, corpoServidores([SERVIDOR_ATIVO]))))
    vi.stubGlobal('fetch', fetchMock)
    abrirCom('/?nome=Maria')
    const sinalPrimeira: AbortSignal = fetchMock.mock.calls[0][1].signal

    navegarPara('/?nome=Joana')
    expect(sinalPrimeira.aborted).toBe(true)
    expect(campoNome()).toHaveValue('Joana')
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('1 resultado encontrado para “Joana”')

    await act(async () => responderPrimeira(respostaJson(200, corpoServidores())))
    expect(tituloResultados()).toHaveTextContent('1 resultado encontrado para “Joana”')
  })

  it(`mostra erro se a API não responde em ${SEARCH_TIMEOUT_MS} ms`, async () => {
    vi.useFakeTimers()
    const { pedidos } = fetchPendente()
    abrirCom('/?nome=Maria')
    expect(regiaoViva()).toHaveTextContent('Buscando…')

    await act(() => vi.advanceTimersByTimeAsync(SEARCH_TIMEOUT_MS))

    expect(pedidos[0].signal.aborted).toBe(true)
    expect(screen.getByRole('alert')).toHaveTextContent('A API não respondeu em 20 segundos')
    expect(botaoBuscar()).toHaveTextContent('Buscar')
  })

  it('fechar a tela cancela a requisição pendente', () => {
    const { pedidos } = fetchPendente()
    const { unmount } = abrirCom('/?nome=Maria')
    unmount()
    expect(pedidos[0].signal.aborted).toBe(true)
  })

  it('no StrictMode a montagem dupla não duplica nada na tela', async () => {
    const { pedidos } = fetchPendente()
    abrirCom(
      '/?nome=Maria',
      <StrictMode>
        <App />
      </StrictMode>,
    )
    expect(pedidos).toHaveLength(2)
    expect(pedidos[0].signal.aborted).toBe(true)
    expect(pedidos[1].signal.aborted).toBe(false)

    await act(async () => pedidos[1].responder(respostaJson(200, corpoServidores())))

    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1)
    expect(screen.getAllByRole('table')).toHaveLength(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
