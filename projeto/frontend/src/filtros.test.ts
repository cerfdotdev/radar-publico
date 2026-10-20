import { describe, expect, it } from 'vitest'
import { LIMITE_MAX, LIMITE_MIN, padraoParecido, validarBusca, validarSimilar, validarTexto } from './filtros'
import { NOME_MAX_CHARS } from './nome'
import type { Busca } from './types'
import { BUSCA_VAZIA } from './useBuscaServidores'

const busca = (campos: Partial<Busca>): Busca => ({ ...BUSCA_VAZIA, ...campos })

describe('validarSimilar (regras de similar em docs/api.md)', () => {
  it.each(['%MARIA%SILVA%', 'maria silva%', '%José%', "%D'AVILA%", 'ANA%'])('aceita %j', (padrao) => {
    expect(validarSimilar(padrao)).toBeNull()
  })

  it.each([
    ['', 'Informe um nome parecido para pesquisar.'],
    ['A', 'O nome parecido deve ter pelo menos 2 caracteres.'],
    [`%${'A'.repeat(NOME_MAX_CHARS)}`, 'O nome parecido deve ter no máximo 100 caracteres.'],
    ['%MARIA1%', "Use só letras, espaços, apóstrofo ('), ponto (.), hífen (-) e o curinga (%)."],
    ['%MARIA_%', "Use só letras, espaços, apóstrofo ('), ponto (.), hífen (-) e o curinga (%)."],
    ['%ANA--MARIA%', 'Não use dois hífens seguidos (--).'],
    ['%AB%', 'Digite pelo menos 3 letras além dos %.'],
    ['%%%%', 'Digite pelo menos 3 letras além dos %.'],
  ])('recusa %j', (padrao, mensagem) => {
    expect(validarSimilar(padrao)).toBe(mensagem)
  })
})

describe('validarTexto (cargo e órgão)', () => {
  it.each(['MINISTERIO DA SAUDE (MS)', 'professor 1/2', 'Saúde, Educação'])('aceita %j', (texto) => {
    expect(validarTexto(texto, 'órgão')).toBeNull()
  })

  it('vazio é filtro não usado; curto, com ; ou com -- é erro', () => {
    expect(validarTexto('  ', 'cargo')).toBeNull()
    expect(validarTexto('a', 'cargo')).toBe('O cargo deve ter pelo menos 2 caracteres.')
    expect(validarTexto('saude; drop', 'órgão')).toMatch(/^Use só letras, números/)
    expect(validarTexto('A--B', 'órgão')).toBe('Não use dois hífens seguidos (--).')
  })
})

describe('validarBusca', () => {
  it('pede um nome ou um filtro; qualquer filtro sozinho basta', () => {
    expect(validarBusca(BUSCA_VAZIA)).toEqual({
      campo: 'termo',
      mensagem: 'Informe um nome ou pelo menos um filtro: cargo, órgão ou UF.',
    })
    expect(validarBusca(busca({ uf: 'RJ' }))).toBeNull()
    expect(validarBusca(busca({ cargo: 'professor' }))).toBeNull()
    expect(validarBusca(busca({ orgao: 'INSS' }))).toBeNull()
  })

  it('aponta o campo com erro, na ordem da tela', () => {
    expect(validarBusca(busca({ termo: 'Maria1', cargo: 'a' }))?.campo).toBe('termo')
    expect(validarBusca(busca({ termo: 'Maria', cargo: 'a' }))?.campo).toBe('cargo')
    expect(validarBusca(busca({ orgao: 'a' }))?.campo).toBe('orgao')
    expect(validarBusca(busca({ uf: 'XX' }))).toEqual({ campo: 'uf', mensagem: 'Escolha uma UF válida.' })
  })

  it.each([Number.NaN, LIMITE_MIN - 1, LIMITE_MAX + 1, 1.5])('busca parecida recusa limite %d', (limite) => {
    expect(validarBusca(busca({ modo: 'similar', termo: '%MARIA%', limite }))).toEqual({
      campo: 'limite',
      mensagem: 'O limite deve ser um número inteiro de 1 a 100.',
    })
  })

  it('busca parecida exige o padrão e ignora cargo, órgão e UF, que ela não envia', () => {
    expect(validarBusca(busca({ modo: 'similar', cargo: 'professor' }))?.campo).toBe('termo')
    expect(validarBusca(busca({ modo: 'similar', termo: '%MARIA%', limite: LIMITE_MIN, cargo: 'a', uf: 'XX' }))).toBeNull()
    expect(validarBusca(busca({ modo: 'similar', termo: '%MARIA%', limite: LIMITE_MAX }))).toBeNull()
  })
})

describe('padraoParecido (sugestão do estado vazio)', () => {
  it('monta o padrão sem acento e sem conectivos', () => {
    expect(padraoParecido('João da Silva Xavier')).toBe('%JOAO%SILVA%XAVIER%')
    expect(padraoParecido("Ana  D'Ávila dos Santos")).toBe("%ANA%D'AVILA%SANTOS%")
  })

  it('não sugere padrão que a API recusaria', () => {
    expect(padraoParecido('Da Do')).toBeNull()
    expect(padraoParecido('Al')).toBeNull()
  })
})
