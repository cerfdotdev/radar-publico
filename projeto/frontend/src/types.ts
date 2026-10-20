// Contrato de GET /api/servidores (docs/api.md).

export type Situacao = 'ativo' | 'aposentado'

/** Como o nome é enviado: exato (`nome`) ou parecido (`similar`). */
export type ModoBusca = 'exato' | 'similar'

/** Filtros combináveis do formulário e da URL. */
export interface Busca {
  modo: ModoBusca
  /** Nome exato ou padrão de similaridade, conforme `modo`. */
  termo: string
  /** Máximo de resultados; só vale para `similar`. */
  limite: number
  cargo: string
  orgao: string
  uf: string
  /** Página da lista de resultados (a partir de 1). */
  pagina: number
  /** Itens por página, de 1 a 100. */
  porPagina: number
}

/** Campo do formulário que recebe um erro de validação, local ou da API. */
export type CampoBusca = 'termo' | 'limite' | 'cargo' | 'orgao' | 'uf'

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
  /** Só na busca por `similar`: semelhança com o padrão, de 0 a 1. */
  similaridade?: number
}

/** GET /api/servidores/<id>: dados da lista mais os campos do vínculo. */
export interface ServidorDetalhe extends Servidor {
  codigo_carreira: string | null
  tipo_aposentadoria: string | null
  fundamento_legal: string | null
  portaria: string | null
  data_aposentadoria: string | null
  forma_ingresso: string | null
  data_ingresso: string | null
  referencia: string | null
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
