import { useEffect, useRef, useState, type FormEvent } from 'react'
import { limparNome, validarNome } from './nome'

interface SearchFormProps {
  /** Termo da busca atual (da URL). */
  termo: string
  /** Busca em andamento: o formulário ignora novos envios. */
  ocupado: boolean
  /** Erro vindo de fora do campo: 400 da API ou nome inválido na URL. */
  erroExterno: string | null
  onBuscar: (termo: string) => void
}

export function SearchForm({ termo, ocupado, erroExterno, onBuscar }: SearchFormProps) {
  const campoRef = useRef<HTMLInputElement>(null)
  const [nome, setNome] = useState(termo)
  const [termoAnterior, setTermoAnterior] = useState(termo)
  const [erroLocal, setErroLocal] = useState<string | null>(null)
  const [editado, setEditado] = useState(false)

  // A busca mudou por fora do campo (voltar ou avançar no navegador): o campo acompanha.
  if (termo !== termoAnterior) {
    setTermoAnterior(termo)
    setNome(termo)
    setErroLocal(null)
    setEditado(false)
  }

  // Erro devolvido pela API ou nome inválido na URL: o foco vai para o campo com erro.
  useEffect(() => {
    if (erroExterno !== null) campoRef.current?.focus()
  }, [erroExterno])

  const erro = erroLocal ?? (editado ? null : erroExterno)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (ocupado) return
    const mensagem = validarNome(nome)
    if (mensagem !== null) {
      setErroLocal(mensagem)
      campoRef.current?.focus()
      return
    }
    setErroLocal(null)
    setEditado(false)
    onBuscar(limparNome(nome))
  }

  return (
    <search aria-label="Buscar servidores">
      <form className="busca" onSubmit={handleSubmit}>
        <div className={erro === null ? 'campo' : 'campo campo--erro'}>
          <div className="busca__nome-topo">
            <label className="campo__rotulo" htmlFor="campo-nome">
              Nome do servidor
            </label>
          </div>
          <div className="busca__linha">
            {/* readOnly e aria-disabled em vez de disabled: o foco fica onde estava durante a busca. */}
            <input
              ref={campoRef}
              className="controle controle--grande"
              id="campo-nome"
              name="nome"
              type="text"
              placeholder="Ex.: Maria da Silva"
              spellCheck={false}
              enterKeyHint="search"
              value={nome}
              onChange={(event) => {
                setNome(event.target.value)
                setErroLocal(null)
                setEditado(true)
              }}
              readOnly={ocupado}
              aria-invalid={erro !== null}
              aria-describedby={erro === null ? 'dica-nome' : 'erro-nome'}
            />
            <button className="btn btn--primario btn--grande" type="submit" aria-disabled={ocupado} aria-busy={ocupado}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" />
              </svg>
              {ocupado ? 'Buscando…' : 'Buscar'}
            </button>
            {erro === null ? (
              <p className="aux" id="dica-nome">
                Digite o nome completo, como no registro.
              </p>
            ) : (
              <p className="campo__erro" id="erro-nome" role="alert">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 8v5M12 16h.01" />
                </svg>
                {erro}
              </p>
            )}
          </div>
        </div>
      </form>
    </search>
  )
}
