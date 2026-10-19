import { describe, expect, it } from 'vitest'
import { formatCurrency } from './format'
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
