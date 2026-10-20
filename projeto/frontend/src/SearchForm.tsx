import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  LIMITE_MAX,
  LIMITE_MIN,
  limparTermo,
  UFS,
  validarBusca,
  type CampoBusca,
  type ErroBusca,
} from './filtros'
import type { Busca } from './types'

interface SearchFormProps {
  /** Busca atual (da URL). */
  busca: Busca
  /** Busca em andamento: o formulário ignora novos envios. */
  ocupado: boolean
  /** Erro vindo de fora do campo: 400 da API ou filtros inválidos na URL. */
  erroExterno: ErroBusca | null
  onBuscar: (busca: Busca) => void
}

export function SearchForm({ busca, ocupado, erroExterno, onBuscar }: SearchFormProps) {
  const campoNomeRef = useRef<HTMLInputElement>(null)
  const campoLimiteRef = useRef<HTMLInputElement>(null)
  const campoCargoRef = useRef<HTMLInputElement>(null)
  const campoOrgaoRef = useRef<HTMLInputElement>(null)
  const campoUfRef = useRef<HTMLSelectElement>(null)
  const [form, setForm] = useState(busca)
  const [buscaAnterior, setBuscaAnterior] = useState(busca)
  const [erroLocal, setErroLocal] = useState<ErroBusca | null>(null)
  const [editado, setEditado] = useState(false)

  // A busca mudou por fora do formulário (voltar ou avançar no navegador): o formulário acompanha.
  if (busca !== buscaAnterior) {
    setBuscaAnterior(busca)
    setForm(busca)
    setErroLocal(null)
    setEditado(false)
  }

  const erro = erroLocal ?? (editado ? null : erroExterno)

  function focarCampo(campo: CampoBusca) {
    switch (campo) {
      case 'limite':
        campoLimiteRef.current?.focus()
        break
      case 'cargo':
        campoCargoRef.current?.focus()
        break
      case 'orgao':
        campoOrgaoRef.current?.focus()
        break
      case 'uf':
        campoUfRef.current?.focus()
        break
      default:
        campoNomeRef.current?.focus()
    }
  }

  // Erro devolvido pela API ou filtro inválido na URL: o foco vai para o campo com erro.
  useEffect(() => {
    if (erroExterno !== null) focarCampo(erroExterno.campo)
  }, [erroExterno])

  function atualizar(campo: keyof Busca, valor: string | number) {
    setForm((atual) => ({ ...atual, [campo]: valor }))
    setErroLocal(null)
    setEditado(true)
  }

  function trocarModo(modo: Busca['modo']) {
    if (ocupado || form.modo === modo) return
    setForm((atual) => ({ ...atual, modo }))
    setErroLocal(null)
    setEditado(true)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (ocupado) return
    const normalizada: Busca = {
      ...form,
      termo: limparTermo(form.termo),
      cargo: limparTermo(form.cargo),
      orgao: limparTermo(form.orgao),
      pagina: 1,
    }
    const mensagem = validarBusca(normalizada)
    if (mensagem !== null) {
      setErroLocal(mensagem)
      focarCampo(mensagem.campo)
      return
    }
    setErroLocal(null)
    setEditado(false)
    setForm(normalizada)
    onBuscar(normalizada)
  }

  const erroTermo = erro?.campo === 'termo' ? erro : null
  const erroLimite = erro?.campo === 'limite' ? erro : null
  const erroCargo = erro?.campo === 'cargo' ? erro : null
  const erroOrgao = erro?.campo === 'orgao' ? erro : null
  const erroUf = erro?.campo === 'uf' ? erro : null
  const similar = form.modo === 'similar'

  return (
    <search aria-label="Buscar servidores">
      <form className="busca" onSubmit={handleSubmit}>
        <div className={erroTermo === null ? 'campo' : 'campo campo--erro'}>
          <div className="busca__nome-topo">
            <label className="campo__rotulo" htmlFor="campo-nome">
              Nome do servidor
            </label>
            <fieldset className="alternador">
              <legend className="sr-only">Como buscar o nome</legend>
              <button
                type="button"
                aria-pressed={!similar}
                aria-disabled={ocupado}
                onClick={() => trocarModo('exato')}
              >
                Nome exato
              </button>
              <button
                type="button"
                aria-pressed={similar}
                aria-disabled={ocupado}
                onClick={() => trocarModo('similar')}
              >
                Nome parecido
              </button>
            </fieldset>
          </div>
          <div className="busca__linha">
            {/* readOnly e aria-disabled em vez de disabled: o foco fica onde estava durante a busca. */}
            <input
              ref={campoNomeRef}
              className={similar ? 'controle controle--grande controle--mono' : 'controle controle--grande'}
              id="campo-nome"
              name={similar ? 'similar' : 'nome'}
              type="text"
              placeholder={similar ? 'Ex.: %MARIA%SILVA%' : 'Ex.: Maria da Silva'}
              spellCheck={false}
              enterKeyHint="search"
              value={form.termo}
              onChange={(event) => atualizar('termo', event.target.value)}
              readOnly={ocupado}
              aria-invalid={erroTermo !== null}
              aria-describedby={erroTermo === null ? 'dica-nome' : 'erro-nome'}
            />
            {similar && (
              <label className="limite">
                Até <span className="sr-only">(limite de resultados)</span>
                <input
                  ref={campoLimiteRef}
                  name="limit"
                  type="number"
                  min={LIMITE_MIN}
                  max={LIMITE_MAX}
                  value={Number.isInteger(form.limite) ? form.limite : ''}
                  onChange={(event) =>
                    atualizar('limite', event.target.value === '' ? Number.NaN : Number(event.target.value))
                  }
                  readOnly={ocupado}
                  aria-invalid={erroLimite !== null}
                  aria-describedby={erroLimite === null ? undefined : 'erro-limite'}
                />
              </label>
            )}
            <button className="btn btn--primario btn--grande" type="submit" aria-disabled={ocupado} aria-busy={ocupado}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" />
              </svg>
              {ocupado ? 'Buscando…' : 'Buscar'}
            </button>
            {erroTermo === null ? (
              <p className="aux" id="dica-nome">
                {similar
                  ? 'Use % no lugar das partes que você não sabe: %MARIA%SILVA%, MARIA SILVA% ou MARIA%SILVA. Pelo menos 3 letras. Mostra os mais parecidos primeiro.'
                  : 'Digite o nome completo, como no registro.'}
              </p>
            ) : (
              <p className="campo__erro" id="erro-nome" role="alert">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 8v5M12 16h.01" />
                </svg>
                {erroTermo.mensagem}
              </p>
            )}
          </div>
        </div>

        <div className="busca__filtros" id="filtros">
          <div className={erroCargo === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-cargo">
              Cargo
            </label>
            <input
              ref={campoCargoRef}
              className="controle"
              id="campo-cargo"
              name="cargo"
              type="text"
              placeholder="Ex.: professor"
              spellCheck={false}
              value={form.cargo}
              onChange={(event) => atualizar('cargo', event.target.value)}
              readOnly={ocupado}
              aria-invalid={erroCargo !== null}
              aria-describedby={erroCargo === null ? undefined : 'erro-cargo'}
            />
            {erroCargo !== null && (
              <p className="campo__erro" id="erro-cargo" role="alert">
                {erroCargo.mensagem}
              </p>
            )}
          </div>

          <div className={erroOrgao === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-orgao">
              Órgão
            </label>
            <input
              ref={campoOrgaoRef}
              className="controle"
              id="campo-orgao"
              name="orgao"
              type="text"
              placeholder="Nome ou sigla, ex.: INSS"
              spellCheck={false}
              value={form.orgao}
              onChange={(event) => atualizar('orgao', event.target.value)}
              readOnly={ocupado}
              aria-invalid={erroOrgao !== null}
              aria-describedby={erroOrgao === null ? undefined : 'erro-orgao'}
            />
            {erroOrgao !== null && (
              <p className="campo__erro" id="erro-orgao" role="alert">
                {erroOrgao.mensagem}
              </p>
            )}
          </div>

          <div className={erroUf === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-uf">
              UF <small>(só ativos)</small>
            </label>
            <select
              ref={campoUfRef}
              className="controle"
              id="campo-uf"
              name="uf"
              value={form.uf}
              onChange={(event) => atualizar('uf', event.target.value)}
              disabled={ocupado}
              aria-invalid={erroUf !== null}
              aria-describedby={erroUf === null ? undefined : 'erro-uf'}
            >
              <option value="">Todas</option>
              {UFS.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
            {erroUf !== null && (
              <p className="campo__erro" id="erro-uf" role="alert">
                {erroUf.mensagem}
              </p>
            )}
          </div>
        </div>

        {erroLimite !== null && (
          <p className="campo__erro" id="erro-limite" role="alert">
            {erroLimite.mensagem}
          </p>
        )}
      </form>
    </search>
  )
}
