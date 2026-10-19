import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { SEARCH_TIMEOUT_MS } from './api'
import {
  corpoServidores,
  erroApi,
  fetchPendente,
  fetchRespondendo,
  respostaJson,
  respostaTexto,
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
const tituloResultados = () => screen.getByRole('heading', { level: 2 })

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
    expect(campoNome()).toHaveAccessibleDescription('Informe um nome para pesquisar.')
    expect(screen.getByRole('alert')).toHaveTextContent('Informe um nome para pesquisar.')
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
    expect(screen.getByText('Mostrando os 2 primeiros.')).toBeInTheDocument()
    expect(regiaoViva()).toHaveTextContent('Mais de 10.000 resultados para “Maria”. Mostrando os 2 primeiros.')
  })

  it('total maior que a página: mostra o total exato e quantos estão na tela', async () => {
    fetchRespondendo(() => respostaJson(200, corpoServidores(undefined, { total: 2345, total_pages: 118 })))
    abrirCom('/?nome=Maria')
    expect(await screen.findByText('Mostrando os 2 primeiros.')).toBeInTheDocument()
    expect(tituloResultados()).toHaveTextContent('2.345 resultados encontrados para “Maria”')
    expect(screen.queryByText('Refine a busca')).not.toBeInTheDocument()
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
