import { describe, expect, it } from 'vitest'
import { formatCurrency, formatDate, formatReference, formatSimilaridade } from './format'
import { limparNome, NOME_MAX_CHARS, normalizarNome, validarNome } from './nome'

describe('nome', () => {
  it('limpa espaços sem mudar acentos nem maiúsculas', () => {
    expect(limparNome('  Maria   da\tSilva ')).toBe('Maria da Silva')
  })

  it('normaliza como o backend: sem acento, maiúsculas e espaços simples', () => {
    expect(normalizarNome("  José  d'Ávila ")).toBe("JOSE D'AVILA")
  })

  it.each([
    ['', 'Informe um nome para pesquisar.'],
    ['   ', 'Informe um nome para pesquisar.'],
    [' a ', 'O nome deve ter pelo menos 2 caracteres.'],
    ['a'.repeat(NOME_MAX_CHARS + 1), 'O nome deve ter no máximo 100 caracteres.'],
    ['Maria1', "Use só letras, espaços, apóstrofo ('), ponto (.) e hífen (-)."],
    ['%MARIA%', "Use só letras, espaços, apóstrofo ('), ponto (.) e hífen (-)."],
    ['Maria; DROP', "Use só letras, espaços, apóstrofo ('), ponto (.) e hífen (-)."],
    ['Ana--Maria', 'Não use dois hífens seguidos (--).'],
  ])('recusa %j', (nome, mensagem) => {
    expect(validarNome(nome)).toBe(mensagem)
  })

  it.each(["João D'Ávila-Souza Jr.", 'Ñandú Çaçapava', `  ${'a'.repeat(NOME_MAX_CHARS)}  `])('aceita %j', (nome) => {
    expect(validarNome(nome)).toBeNull()
  })
})

describe('formatCurrency', () => {
  it('formata em pt-BR com duas casas', () => {
    expect(formatCurrency(19090.67)).toBe('19.090,67')
  })

  it('nunca mostra NaN', () => {
    expect(formatCurrency(Number.NaN)).toBe('—')
    expect(formatCurrency(Number.POSITIVE_INFINITY)).toBe('—')
  })
})

describe('datas e semelhança', () => {
  it('datas ISO da API viram DD/MM/AAAA e o mês de referência MM/AAAA', () => {
    expect(formatDate('1990-07-02')).toBe('02/07/1990')
    expect(formatReference('2026-05')).toBe('05/2026')
  })

  it('fora do formato, devolvem o texto como veio', () => {
    expect(formatDate('02/07/1990')).toBe('02/07/1990')
    expect(formatDate('1990-7-2')).toBe('1990-7-2')
    expect(formatReference('maio de 2026')).toBe('maio de 2026')
  })

  it('semelhança com duas casas, em pt-BR', () => {
    expect(formatSimilaridade(0.8571)).toBe('0,86')
    expect(formatSimilaridade(1)).toBe('1,00')
  })
})
