import { afterEach, describe, expect, it, vi } from 'vitest'
import { buscarServidores, parseServidoresResponse, SEARCH_TIMEOUT_MS, type SearchOutcome } from './api'
import {
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
})

async function buscarCom(resposta: Response): Promise<SearchOutcome> {
  fetchRespondendo(() => resposta)
  return buscarServidores('Maria da Silva', new AbortController().signal)
}

function falhaDe(resultado: SearchOutcome) {
  if (resultado.kind !== 'error') throw new Error(`esperava erro, veio ${resultado.kind}`)
  return resultado.falha
}

describe('buscarServidores', () => {
  it('monta a query com URLSearchParams e pede JSON', async () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    await buscarServidores("João D'Ávila", new AbortController().signal)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/servidores?nome=Jo%C3%A3o+D%27%C3%81vila',
      expect.objectContaining({ headers: { Accept: 'application/json' }, signal: expect.any(AbortSignal) }),
    )
  })

  it('devolve os servidores e o meta de uma resposta 200 válida', async () => {
    const resultado = await buscarCom(respostaJson(200, corpoServidores()))
    expect(resultado).toEqual({
      kind: 'ok',
      servidores: [SERVIDOR_ATIVO, SERVIDOR_APOSENTADO],
      meta: { total: 2, total_exato: true, page: 1, per_page: 20, total_pages: 1 },
    })
  })

  it('trata 404 NAO_ENCONTRADO como busca sem resultado, não como erro', async () => {
    const resultado = await buscarCom(erroApi(404, 'NAO_ENCONTRADO', 'Nenhum servidor encontrado.'))
    expect(resultado).toEqual({ kind: 'empty' })
  })

  it('trata lista vazia num 200 também como busca sem resultado', async () => {
    const resultado = await buscarCom(respostaJson(200, corpoServidores([], { total: 0, total_pages: 0 })))
    expect(resultado).toEqual({ kind: 'empty' })
  })

  it('outro 404 é erro, com a mensagem da API', async () => {
    const falha = falhaDe(await buscarCom(erroApi(404, 'ROTA_INEXISTENTE', 'Rota não encontrada.')))
    expect(falha).toMatchObject({ tom: 'erro', texto: 'Rota não encontrada.' })
  })

  it('monta a query da busca parecida e dos filtros combinados, sem parâmetros vazios', async () => {
    const fetchMock = fetchRespondendo(() => respostaJson(200, corpoServidores()))
    await buscarServidores({ similar: '%MARIA%SILVA%', limit: 50 }, new AbortController().signal)
    await buscarServidores({ nome: 'Maria', cargo: 'professor', orgao: 'INSS', uf: 'RJ' }, new AbortController().signal)
    await buscarServidores({ cargo: 'professor', orgao: '' }, new AbortController().signal)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/servidores?similar=%25MARIA%25SILVA%25&limit=50', expect.anything())
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/servidores?nome=Maria&cargo=professor&orgao=INSS&uf=RJ',
      expect.anything(),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/servidores?cargo=professor', expect.anything())
  })

  it.each([
    [
      '404 CARGO_NAO_ENCONTRADO',
      erroApi(404, 'CARGO_NAO_ENCONTRADO', 'Nenhum cargo corresponde à busca.'),
      { campo: 'cargo', message: 'Nenhum cargo contém “pofessor”. Confira a grafia ou use só uma parte do nome do cargo.' },
    ],
    [
      '404 ORGAO_NAO_ENCONTRADO',
      erroApi(404, 'ORGAO_NAO_ENCONTRADO', 'Nenhum órgão corresponde à busca.'),
      { campo: 'orgao', message: 'Nenhum órgão tem “XYZ” no nome ou na sigla. Confira a grafia ou use a sigla, como INSS.' },
    ],
    [
      '400 UF_INVALIDA',
      erroApi(400, 'UF_INVALIDA', "UF 'XX' não existe. Use uma das 27 siglas."),
      { campo: 'uf', message: "UF 'XX' não existe. Use uma das 27 siglas." },
    ],
    [
      "400 citando 'limit'",
      erroApi(400, 'PARAMETRO_INVALIDO', "'limit' deve estar entre 1 e 100."),
      { campo: 'limite', message: "'limit' deve estar entre 1 e 100." },
    ],
    [
      "400 citando 'similar'",
      erroApi(400, 'PARAMETRO_INVALIDO', "'similar' precisa de pelo menos 3 letras fora dos '%'."),
      { campo: 'termo', message: "'similar' precisa de pelo menos 3 letras fora dos '%'." },
    ],
    [
      '400 sem parâmetro na mensagem',
      erroApi(400, 'PARAMETRO_INVALIDO', "Os parâmetros 'nome' e 'similar' não podem ser usados juntos."),
      { campo: 'termo', message: "Os parâmetros 'nome' e 'similar' não podem ser usados juntos." },
    ],
  ])('%s vira erro no campo certo', async (_caso, resposta, esperado) => {
    fetchRespondendo(() => resposta)
    const resultado = await buscarServidores({ cargo: 'pofessor', orgao: 'XYZ' }, new AbortController().signal)
    expect(resultado).toEqual({ kind: 'invalid', ...esperado })
  })

  it('400 vira erro de campo com a mensagem da API', async () => {
    const resultado = await buscarCom(erroApi(400, 'PARAMETRO_INVALIDO', "'nome' contém caracteres não permitidos."))
    expect(resultado).toEqual({ kind: 'invalid', campo: 'termo', message: "'nome' contém caracteres não permitidos." })
  })

  it('429 e 503 têm tom informativo e repetem os segundos do Retry-After', async () => {
    const limite = falhaDe(
      await buscarCom(erroApi(429, 'MUITAS_REQUISICOES', 'Muitas requisições.', { 'Retry-After': '12' })),
    )
    expect(limite).toMatchObject({ tom: 'info', titulo: 'Muitas buscas em pouco tempo' })
    expect(limite.texto).toContain('Você pode buscar de novo em 12 segundos.')

    const ocupado = falhaDe(await buscarCom(erroApi(503, 'SERVIDOR_OCUPADO', 'Ocupado.', { 'Retry-After': '1' })))
    expect(ocupado).toMatchObject({ tom: 'info', titulo: 'O serviço está ocupado' })
    expect(ocupado.texto).toContain('em 1 segundo.')
  })

  it('ignora Retry-After em formato de data', async () => {
    const falha = falhaDe(
      await buscarCom(
        erroApi(429, 'MUITAS_REQUISICOES', 'Muitas requisições.', { 'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT' }),
      ),
    )
    expect(falha.texto).toContain('Tente de novo em instantes.')
  })

  it('502 em HTML é "fora do ar", não "resposta sem JSON"', async () => {
    const falha = falhaDe(await buscarCom(respostaTexto(502, '<html><body>Bad Gateway</body></html>')))
    expect(falha).toMatchObject({ tom: 'erro', titulo: 'A API está fora do ar' })
  })

  it('dá títulos próprios para 502, 504 e 500 do contrato', async () => {
    expect(falhaDe(await buscarCom(erroApi(502, 'SERVIDOR_INDISPONIVEL', 'Indisponível.'))).titulo).toBe(
      'A API está fora do ar',
    )
    expect(falhaDe(await buscarCom(erroApi(504, 'TEMPO_ESGOTADO', 'Demorou.'))).titulo).toBe(
      'A busca demorou demais e foi interrompida',
    )
    expect(falhaDe(await buscarCom(erroApi(500, 'ERRO_INTERNO', 'Erro.'))).titulo).toBe('Algo deu errado do nosso lado')
  })

  it('200 que não é JSON vira erro próprio', async () => {
    const falha = falhaDe(await buscarCom(respostaTexto(200, '<!doctype html><html></html>')))
    expect(falha.titulo).toBe('A API respondeu, mas não em JSON')
  })

  it('200 fora do formato do contrato vira erro, sem quebrar a tela', async () => {
    const falha = falhaDe(await buscarCom(respostaJson(200, { data: 'oops', meta: null })))
    expect(falha.titulo).toBe('Resposta inesperada da API')
  })

  it('falha de rede vira "não foi possível conectar"', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    const falha = falhaDe(await buscarServidores('Maria', new AbortController().signal))
    expect(falha.titulo).toBe('Não foi possível conectar à API')
  })

  it(`desiste depois de ${SEARCH_TIMEOUT_MS} ms e mostra o tempo limite`, async () => {
    vi.useFakeTimers()
    const { pedidos } = fetchPendente()
    const promessa = buscarServidores('Maria', new AbortController().signal)
    await vi.advanceTimersByTimeAsync(SEARCH_TIMEOUT_MS)
    expect(pedidos[0].signal.aborted).toBe(true)
    expect(falhaDe(await promessa).titulo).toBe('A API não respondeu em 20 segundos')
  })

  it('rejeita com AbortError quando quem chamou cancela', async () => {
    const { pedidos } = fetchPendente()
    const controller = new AbortController()
    const promessa = buscarServidores('Maria', controller.signal)
    controller.abort()
    await expect(promessa).rejects.toMatchObject({ name: 'AbortError' })
    expect(pedidos[0].signal.aborted).toBe(true)
  })

  it('nem chama a API se já veio cancelada', async () => {
    const { fetchMock } = fetchPendente()
    const controller = new AbortController()
    controller.abort()
    await expect(buscarServidores('Maria', controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('parseServidoresResponse', () => {
  it('aceita campos null do contrato, valor null e ignora campos a mais', () => {
    const item = { ...SERVIDOR_APOSENTADO, valor: null, campo_novo: 'x' }
    const resultado = parseServidoresResponse(corpoServidores([item as typeof SERVIDOR_APOSENTADO]))
    expect(resultado?.data[0]).toStrictEqual({ ...SERVIDOR_APOSENTADO, valor: null })
  })

  it('mantém a similaridade da busca parecida', () => {
    const resultado = parseServidoresResponse(corpoServidores([{ ...SERVIDOR_ATIVO, similaridade: 0.82 }]))
    expect(resultado?.data[0]).toEqual({ ...SERVIDOR_ATIVO, similaridade: 0.82 })
  })

  it.each([
    ['data que não é lista', { ...corpoServidores(), data: 'oops' }],
    ['meta ausente', { data: [SERVIDOR_ATIVO] }],
    ['total_exato que não é booleano', corpoServidores([SERVIDOR_ATIVO], { total_exato: 'sim' as unknown as boolean })],
    ['item sem valor', corpoServidores([{ ...SERVIDOR_ATIVO, valor: undefined as unknown as number }])],
    ['valor em texto', corpoServidores([{ ...SERVIDOR_ATIVO, valor: '19090,67' as unknown as number }])],
    ['situação desconhecida', corpoServidores([{ ...SERVIDOR_ATIVO, situacao: 'pensionista' as 'ativo' }])],
    ['uf ausente', corpoServidores([{ ...SERVIDOR_ATIVO, uf: undefined as unknown as null }])],
    ['similaridade acima de 1', corpoServidores([{ ...SERVIDOR_ATIVO, similaridade: 1.5 }])],
    ['similaridade em texto', corpoServidores([{ ...SERVIDOR_ATIVO, similaridade: '0,82' as unknown as number }])],
  ])('recusa %s', (_caso, corpo) => {
    expect(parseServidoresResponse(JSON.parse(JSON.stringify(corpo)))).toBeNull()
  })
})
