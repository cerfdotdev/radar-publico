import { SEM_VALOR } from './format'

/**
 * Campo null na API: travessão na tela e "não informado" para leitores de tela.
 * Texto oculto em vez de aria-label, que não vale num <span> sem papel (ARIA 1.2).
 */
export function NaoInformado() {
  return (
    <>
      <span aria-hidden="true">{SEM_VALOR}</span>
      <span className="sr-only">não informado</span>
    </>
  )
}
