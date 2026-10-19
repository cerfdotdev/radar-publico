import type { Situacao } from './types'

/** Situação do vínculo: marcador cheio (ativo) ou vazado (aposentado), nunca só cor. */
export function SituacaoPill({ situacao }: { situacao: Situacao }) {
  if (situacao === 'ativo') {
    return (
      <span className="pilula pilula--ativo">
        <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
          <circle cx="4" cy="4" r="4" fill="currentColor" />
        </svg>
        Ativo
      </span>
    )
  }
  return (
    <span className="pilula pilula--aposentado">
      <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
        <circle cx="4" cy="4" r="3" fill="none" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      Aposentado
    </span>
  )
}
