import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import type { ServidoresResponse } from './types'

const mockServidoresResponse: ServidoresResponse = {
  data: [
    {
      id: 1048213,
      nome: 'MARIA DA SILVA',
      situacao: 'ativo',
      cargo: 'ANALISTA DE FINANCAS E CONTROLE',
      orgao: 'CONTROLADORIA-GERAL DA UNIAO',
      sigla_orgao: null,
      uf: 'DF',
      valor: 19090.67,
    },
    {
      id: 1503377,
      nome: 'MARIA DA SILVA SANTOS',
      situacao: 'aposentado',
      cargo: 'AGENTE ADMINISTRATIVO',
      orgao: 'MINISTERIO DA AGRICULTURA E PECUARIA',
      sigla_orgao: 'MAPA',
      uf: null,
      valor: 7006.78,
    },
  ],
  meta: {
    total: 2,
    total_exato: true,
    page: 1,
    per_page: 20,
    total_pages: 1,
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('Tela de Busca do Radar Público (Issue #11)', () => {
  it('renderiza o cabeçalho com logo, título e links de navegação', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: /buscar servidores federais/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /radar público/i })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /principal/i })).toBeInTheDocument()
    expect(document.querySelector('search')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /buscar/i })).toBeInTheDocument()
  })

  it('exibe erro de validação quando o nome está vazio ou tem menos de 2 caracteres', async () => {
    render(<App />)
    const botaoBuscar = screen.getByRole('button', { name: /buscar/i })

    // Busca vazia
    fireEvent.click(botaoBuscar)
    expect(await screen.findByRole('alert')).toHaveTextContent(/informe um nome para pesquisar/i)

    // Busca com 1 caractere
    const inputNome = screen.getByRole('textbox', { name: /nome do servidor/i })
    fireEvent.change(inputNome, { target: { value: 'A' } })
    fireEvent.click(botaoBuscar)
    expect(await screen.findByRole('alert')).toHaveTextContent(/pelo menos 2 caracteres/i)
  })

  it('consome a API e renderiza os resultados na tabela e na lista responsiva', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockServidoresResponse),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    const inputNome = screen.getByRole('textbox', { name: /nome do servidor/i })
    const botaoBuscar = screen.getByRole('button', { name: /buscar/i })

    fireEvent.change(inputNome, { target: { value: 'Maria da Silva' } })
    fireEvent.click(botaoBuscar)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/servidores?nome=Maria%20da%20Silva')
    })

    // Cabeçalho de resultados
    expect(await screen.findByText(/2 resultados encontrados para “Maria da Silva”/i)).toBeInTheDocument()

    // Servidores na tabela
    expect(screen.getAllByText('MARIA DA SILVA').length).toBeGreaterThan(0)
    expect(screen.getAllByText('MARIA DA SILVA SANTOS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('ANALISTA DE FINANCAS E CONTROLE').length).toBeGreaterThan(0)
    expect(screen.getAllByText('CONTROLADORIA-GERAL DA UNIAO').length).toBeGreaterThan(0)

    // Pílulas de situação
    expect(screen.getAllByText(/ativo/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/aposentado/i).length).toBeGreaterThan(0)

    // Valores formatados
    expect(screen.getAllByText(/19\.090,67/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/7\.006,78/).length).toBeGreaterThan(0)

    // UF ausente formatado como travessão
    expect(screen.getByLabelText('não informado')).toBeInTheDocument()
  })

  it('exibe estado vazio quando nenhum servidor é encontrado', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ data: [], meta: { total: 0, total_exato: true, page: 1, per_page: 20, total_pages: 0 } }),
      }),
    )

    render(<App />)
    const inputNome = screen.getByRole('textbox', { name: /nome do servidor/i })
    const botaoBuscar = screen.getByRole('button', { name: /buscar/i })

    fireEvent.change(inputNome, { target: { value: 'Inexistente' } })
    fireEvent.click(botaoBuscar)

    expect(await screen.findByRole('heading', { name: /nenhum resultado encontrado/i })).toBeInTheDocument()
  })

  it('exibe aviso de erro quando a API falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { message: 'Erro interno no servidor' } }),
      }),
    )

    render(<App />)
    const inputNome = screen.getByRole('textbox', { name: /nome do servidor/i })
    const botaoBuscar = screen.getByRole('button', { name: /buscar/i })

    fireEvent.change(inputNome, { target: { value: 'Maria' } })
    fireEvent.click(botaoBuscar)

    expect(await screen.findByRole('alert')).toHaveTextContent(/erro interno no servidor/i)
  })
})
