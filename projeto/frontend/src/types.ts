// Contrato de GET /api/servidores (docs/api.md).

export type Situacao = 'ativo' | 'aposentado'

export interface Servidor {
  id: number
  nome: string
  situacao: Situacao
  // Campos ausentes na fonte vêm null: cargo em alguns aposentados, sigla só existe
  // para aposentados e uf só para ativos.
  cargo: string | null
  orgao: string
  sigla_orgao: string | null
  uf: string | null
  // O contrato diz número, mas a coluna aceita NULL e o backend repassa null.
  valor: number | null
}

export interface Meta {
  total: number
  total_exato: boolean
  page: number
  per_page: number
  total_pages: number
}

export interface ServidoresResponse {
  data: Servidor[]
  meta: Meta
}

export interface ApiError {
  code: string
  message: string
}
