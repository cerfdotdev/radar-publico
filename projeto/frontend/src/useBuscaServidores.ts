import { useCallback, useEffect, useState } from 'react'
import { buscarServidores, FALHA_INESPERADA, type SearchOutcome } from './api'
import { limparNome, validarNome } from './nome'

/** Parâmetro da URL com a busca: recarregar, copiar o link e voltar mantêm a busca. */
export const NOME_PARAM = 'nome'

export type SearchState =
  | { kind: 'idle' }
  | { kind: 'loading'; termo: string }
  | (SearchOutcome & { termo: string })

// Cada busca é um objeto novo: repetir o mesmo termo também refaz a requisição,
// e a resposta só vale para o objeto que a pediu.
interface Busca {
  termo: string
}

interface Resposta {
  busca: Busca
  resultado: SearchOutcome
}

function lerBuscaDaUrl(): Busca | null {
  const termo = limparNome(new URLSearchParams(window.location.search).get(NOME_PARAM) ?? '')
  return termo === '' ? null : { termo }
}

function estadoAtual(busca: Busca | null, resposta: Resposta | null): SearchState {
  if (busca === null) return { kind: 'idle' }
  const erro = validarNome(busca.termo)
  if (erro !== null) return { kind: 'invalid', termo: busca.termo, message: erro }
  if (resposta?.busca !== busca) return { kind: 'loading', termo: busca.termo }
  return { ...resposta.resultado, termo: busca.termo }
}

/** Busca por nome guardada na URL (?nome=), com cancelamento da requisição anterior. */
export function useBuscaServidores() {
  const [busca, setBusca] = useState(lerBuscaDaUrl)
  const [resposta, setResposta] = useState<Resposta | null>(null)

  // Voltar e avançar no navegador: a URL é a fonte da verdade da busca.
  useEffect(() => {
    const aoNavegar = () => setBusca(lerBuscaDaUrl())
    window.addEventListener('popstate', aoNavegar)
    return () => window.removeEventListener('popstate', aoNavegar)
  }, [])

  // Uma requisição por busca. Trocar de busca ou desmontar a tela cancela a anterior,
  // e uma resposta cancelada nunca sobrescreve a atual (nem no StrictMode, que monta
  // o efeito duas vezes em desenvolvimento).
  useEffect(() => {
    if (busca === null || validarNome(busca.termo) !== null) return
    const controller = new AbortController()
    buscarServidores(busca.termo, controller.signal).then(
      (resultado) => {
        if (!controller.signal.aborted) setResposta({ busca, resultado })
      },
      () => {
        // buscarServidores só rejeita quando cancelada; outro motivo não pode travar a tela.
        if (!controller.signal.aborted) {
          setResposta({ busca, resultado: { kind: 'error', falha: FALHA_INESPERADA } })
        }
      },
    )
    return () => controller.abort()
  }, [busca])

  const buscar = useCallback((termo: string) => {
    const url = new URL(window.location.href)
    const mesmaBusca = url.searchParams.get(NOME_PARAM) === termo
    url.searchParams.set(NOME_PARAM, termo)
    // Repetir a busca atual não empilha outra entrada igual no histórico.
    if (mesmaBusca) {
      window.history.replaceState(null, '', url)
    } else {
      window.history.pushState(null, '', url)
    }
    setBusca({ termo })
  }, [])

  return { termo: busca?.termo ?? '', state: estadoAtual(busca, resposta), buscar }
}
