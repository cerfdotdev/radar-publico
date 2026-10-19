export interface Servidor {
  id: number
  nome: string
  situacao: 'ativo' | 'aposentado'
  cargo: string
  orgao: string
  sigla_orgao?: string | null
  uf?: string | null
  valor: number
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

export interface ApiErrorResponse {
  error?: {
    code?: string
    message?: string
  }
}
