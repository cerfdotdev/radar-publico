import { useLayoutEffect, useState, type FormEvent } from 'react'
import {
  LIMITE_MAX,
  LIMITE_MIN,
  SIMILAR_MIN_LETRAS_SEGUIDAS,
  UFS,
  validarBusca,
  type ErroBusca,
} from './filtros'
import { limparNome } from './nome'
import type { Busca, CampoBusca, ModoBusca } from './types'

interface SearchFormProps {
  /** Busca atual (da URL). */
  busca: Busca
  /** Busca em andamento: o formulário ignora novos envios. */
  ocupado: boolean
  /** Erro vindo de fora do formulário: resposta da API ou filtros inválidos na URL. */
  erroExterno: ErroBusca | null
  onBuscar: (busca: Busca) => void
}

// Controle de cada campo, para levar o foco até o que tem erro.
const ID_DO_CAMPO: Record<CampoBusca, string> = {
  termo: 'campo-nome',
  limite: 'campo-limite',
  cargo: 'campo-cargo',
  orgao: 'campo-orgao',
  uf: 'campo-uf',
}

function focarCampo(campo: CampoBusca) {
  document.getElementById(ID_DO_CAMPO[campo])?.focus()
}

export function SearchForm({ busca, ocupado, erroExterno, onBuscar }: SearchFormProps) {
  const [form, setForm] = useState(busca)
  const [buscaAnterior, setBuscaAnterior] = useState(busca)
  const [erroLocal, setErroLocal] = useState<ErroBusca | null>(null)
  const [editado, setEditado] = useState(false)
  // Só no celular: os filtros ficam recolhidos atrás do botão "Filtros".
  const [filtrosAbertos, setFiltrosAbertos] = useState(false)

  // A busca mudou por fora do formulário (voltar ou avançar no navegador): o formulário acompanha.
  if (busca !== buscaAnterior) {
    setBuscaAnterior(busca)
    setForm(busca)
    setErroLocal(null)
    setEditado(false)
  }

  // Erro devolvido pela API ou filtro inválido na URL: o foco vai para o campo com erro.
  // Depende só do campo e do texto, não do objeto, que é novo a cada render. useLayoutEffect
  // move o foco junto com a mensagem de erro, antes da pintura, e não um instante depois.
  const campoExterno = erroExterno?.campo ?? null
  const mensagemExterna = erroExterno?.mensagem ?? null
  useLayoutEffect(() => {
    if (campoExterno !== null) focarCampo(campoExterno)
  }, [campoExterno, mensagemExterna])

  const erro = erroLocal ?? (editado ? null : erroExterno)
  const erroDe = (campo: CampoBusca) => (erro?.campo === campo ? erro.mensagem : null)

  function atualizar<K extends keyof Busca>(campo: K, valor: Busca[K]) {
    setForm((atual) => ({ ...atual, [campo]: valor }))
    setErroLocal(null)
    setEditado(true)
  }

  function trocarModo(modo: ModoBusca) {
    if (ocupado || form.modo === modo) return
    atualizar('modo', modo)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (ocupado) return
    const normalizada: Busca = {
      ...form,
      termo: limparNome(form.termo),
      cargo: limparNome(form.cargo),
      orgao: limparNome(form.orgao),
      pagina: 1,
    }
    const erroNovo = validarBusca(normalizada)
    if (erroNovo !== null) {
      setErroLocal(erroNovo)
      focarCampo(erroNovo.campo)
      return
    }
    setErroLocal(null)
    setEditado(false)
    setForm(normalizada)
    onBuscar(normalizada)
  }

  const erroTermo = erroDe('termo')
  const erroLimite = erroDe('limite')
  const erroCargo = erroDe('cargo')
  const erroOrgao = erroDe('orgao')
  const erroUf = erroDe('uf')
  const similar = form.modo === 'similar'
  const filtrosPreenchidos = [form.cargo, form.orgao, form.uf].filter((valor) => valor.trim() !== '').length
  // Um filtro com erro fica sempre à vista, para receber o foco.
  const filtrosVisiveis = filtrosAbertos || erroCargo !== null || erroOrgao !== null || erroUf !== null

  return (
    <search aria-label="Buscar servidores">
      {/* noValidate: o min/max do limite não pode barrar o envio com o balão do navegador;
          a validação é a nossa, no próprio campo e com o foco nele. */}
      <form className="busca" onSubmit={handleSubmit} noValidate>
        <div className={erroTermo === null ? 'campo' : 'campo campo--erro'}>
          <div className="busca__nome-topo">
            <label className="campo__rotulo" htmlFor="campo-nome">
              Nome do servidor
            </label>
            <fieldset className="alternador">
              <legend className="sr-only">Como buscar o nome</legend>
              <button type="button" aria-pressed={!similar} aria-disabled={ocupado} onClick={() => trocarModo('exato')}>
                Nome exato
              </button>
              <button type="button" aria-pressed={similar} aria-disabled={ocupado} onClick={() => trocarModo('similar')}>
                Nome parecido
              </button>
            </fieldset>
          </div>
          <div className="busca__linha">
            {/* readOnly e aria-disabled em vez de disabled: o foco fica onde estava durante a busca. */}
            <input
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
                Até <span className="sr-only">(máximo de resultados)</span>
                <input
                  id="campo-limite"
                  name="limit"
                  type="number"
                  inputMode="numeric"
                  min={LIMITE_MIN}
                  max={LIMITE_MAX}
                  value={Number.isNaN(form.limite) ? '' : form.limite}
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
                  ? `Use % no lugar das partes que você não sabe: %MARIA%SILVA%, MARIA SILVA% ou MARIA%SILVA. Pelo menos um trecho com ${SIMILAR_MIN_LETRAS_SEGUIDAS} letras seguidas. Mostra os mais parecidos primeiro.`
                  : 'Digite o nome completo, como no registro.'}
              </p>
            ) : (
              <ErroCampo id="erro-nome" mensagem={erroTermo} />
            )}
            {erroLimite !== null && <ErroCampo id="erro-limite" mensagem={erroLimite} />}
          </div>
        </div>

        <button
          className="busca__abrir-filtros"
          type="button"
          aria-expanded={filtrosVisiveis}
          aria-controls="filtros"
          aria-label={
            filtrosPreenchidos === 0
              ? 'Filtros'
              : `Filtros, ${filtrosPreenchidos} ${filtrosPreenchidos === 1 ? 'preenchido' : 'preenchidos'}`
          }
          onClick={() => setFiltrosAbertos(!filtrosVisiveis)}
        >
          <span>
            Filtros {filtrosPreenchidos > 0 && <span className="contador">{filtrosPreenchidos}</span>}
          </span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {/* Valem nos dois modos: a API combina os filtros com o nome exato ou parecido. */}
        <fieldset
          id="filtros"
          className={filtrosVisiveis ? 'busca__filtros busca__filtros--aberto' : 'busca__filtros'}
        >
          <legend className="sr-only">Filtros</legend>

          <div className={erroCargo === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-cargo">
              Cargo
            </label>
            <input
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
            {erroCargo !== null && <ErroCampo id="erro-cargo" mensagem={erroCargo} />}
          </div>

          <div className={erroOrgao === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-orgao">
              Órgão
            </label>
            <input
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
            {erroOrgao !== null && <ErroCampo id="erro-orgao" mensagem={erroOrgao} />}
          </div>

          <div className={erroUf === null ? 'campo' : 'campo campo--erro'}>
            <label className="campo__rotulo" htmlFor="campo-uf">
              UF <small>(só ativos)</small>
            </label>
            {/* Sem disabled durante a busca: o foco não sai do campo; trocar a UF só vale no próximo envio. */}
            <select
              className="controle"
              id="campo-uf"
              name="uf"
              value={form.uf}
              onChange={(event) => atualizar('uf', event.target.value)}
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
            {erroUf !== null && <ErroCampo id="erro-uf" mensagem={erroUf} />}
          </div>
        </fieldset>
      </form>
    </search>
  )
}

/** Mensagem de erro abaixo do campo: ícone e texto, nunca só a cor (docs/DESIGN.md). */
function ErroCampo({ id, mensagem }: { id: string; mensagem: string }) {
  return (
    <p className="campo__erro" id={id} role="alert">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v5M12 16h.01" />
      </svg>
      {mensagem}
    </p>
  )
}
