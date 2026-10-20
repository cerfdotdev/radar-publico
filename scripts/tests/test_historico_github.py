"""Histórico do GitHub por integrante, com um repositório pequeno de exemplo.

O exemplo (dados/historico.json) tem 5 issues, 6 PRs e 11 commits na main: um commit direto na
main, um PR de cada integrante, correções e um merge de atualização do líder no PR do João, um
PR aberto, um do Dependabot, um fechado sem merge, um autor sem conta e um commit depois do
momento pedido.
"""

import json
from collections import Counter
from datetime import UTC, date, datetime

import pytest

import burndown as bd
import historico_github as hg

DADOS = hg.Path(__file__).parent / "dados" / "historico.json"
AGORA = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # 20/10 12:00 em Brasília
PLANEJADO = [
    {"issue": 1, "login": "cerfdotdev"},
    {"issue": 2, "login": "cerfdotdev"},
    {"issue": 3, "login": "joaoarenda"},
    {"issue": 4, "login": "Alisson-dutra"},
]
LIDER, JOAO, ALISSON = (m.login for m in hg.EQUIPE)
DIAS = (date(2026, 10, 18), date(2026, 10, 19), date(2026, 10, 20))


def oid(prefixo: str) -> str:
    """Os oids do exemplo repetem o prefixo até 40 caracteres."""
    return (prefixo * 40)[:40]


@pytest.fixture
def bruto():
    return json.loads(DADOS.read_text(encoding="utf-8"))


@pytest.fixture
def hist(bruto):
    return hg.montar(bruto, hg.ler_planejado(PLANEJADO), AGORA)


# ---------------------------------------------------------------- leitura


def test_ler_git_log_com_separadores_de_controle():
    texto = (
        f"{oid('c1')}\x1f{oid('c0')}\x1f2026-10-18T23:05:00-03:00\x1fCarlos Rodrigues"
        "\x1flider@exemplo.com\x1ffix: barra | e % no assunto\x1e\n"
        f"{oid('c0')}\x1f\x1f2026-10-18T22:28:00-03:00\x1fCarlos Rodrigues"
        "\x1flider@exemplo.com\x1fchore: início\x1e\n"
    )
    registros = hg.ler_git_log(texto)
    assert [r["assunto"] for r in registros] == ["fix: barra | e % no assunto", "chore: início"]
    assert registros[0]["pais"] == [oid("c0")] and registros[1]["pais"] == []
    commits = hg.ler_commits(registros)
    assert [c.curto for c in commits] == ["c0c0c0c", "c1c1c1c"]  # em ordem de autoria
    assert commits[0].momento == datetime(2026, 10, 19, 1, 28, tzinfo=UTC)


def test_login_de_bot_ganha_sufixo_e_vira_automacao():
    assert hg.login_ator({"__typename": "Bot", "login": "dependabot"}) == "dependabot[bot]"
    assert hg.login_ator({"__typename": "User", "login": JOAO}) == JOAO
    assert hg.login_ator(None) == hg.SEM_CONTA
    assert hg.categoria("dependabot[bot]") == hg.AUTOMACAO
    assert hg.categoria("alguem") == hg.OUTROS
    assert hg.categoria(ALISSON) == ALISSON


def test_issue_reaberta_ignora_fechamento_antigo(bruto):
    no = bruto["repositorio"]["issues"][1]
    no["state"] = "OPEN"
    (issue,) = hg.ler_issues([no])
    assert issue.fechada is None and issue.fechada_pelo_pr is None


def test_como_cada_issue_fechou(hist):
    assert hg.como_fechou(hist.issues[2]).startswith("pelo PR [#10]")
    assert hg.como_fechou(hist.issues[3]) == "manual por @cerfdotdev"
    assert hg.como_fechou(hist.issues[5]).startswith("pelo commit [`c4c4c4c`]")
    assert hg.como_fechou(hist.issues[1]) == "—"


def test_aviso_de_conexao_incompleta(bruto):
    no = bruto["repositorio"]["prs"][1]
    no["commits"]["totalCount"] = hg.MAX_COMMITS_POR_PR + 1
    _, avisos = hg.ler_prs([no])
    assert avisos == ["PR #11: só parte de commits foi lida"]


# ---------------------------------------------------------------- autores e PRs


def test_autores_pelo_github_sem_tabela_de_emails(hist):
    assert hist.autores[oid("c0")] == LIDER  # fora de PR: e-mail aprendido nos PRs
    assert hist.autores[oid("a10")] == LIDER  # noreply do GitHub
    assert hist.autores[oid("c2")] == JOAO
    assert hist.autores[oid("c4")] == ALISSON
    assert hist.autores[oid("e0")] == hg.OUTROS
    assert "autor sem conta do GitHub identificada: Visitante" in hist.avisos
    contas = {(nome, login, origem) for nome, login, origem, _ in hist.contas}
    assert ("Carlos Rodrigues", LIDER, "e-mail noreply do GitHub") in contas
    assert ("Carlos Rodrigues", LIDER, "autor dos commits nos PRs") in contas


def test_mesmo_email_com_duas_contas_avisa(bruto):
    prs, _ = hg.ler_prs(bruto["repositorio"]["prs"])
    commits = hg.ler_commits(bruto["git"]["commits"])
    trocado = [hg.CommitPr(oid("c1"), JOAO, "Carlos Rodrigues", False)]
    prs.append(hg.PullRequest(**{**prs[0].__dict__, "numero": 99, "commits": tuple(trocado)}))
    _, _, avisos = hg.resolver_autores(commits, prs)
    assert any("aparece com as contas cerfdotdev e joaoarenda" in a for a in avisos)


def test_pr_de_cada_commit(hist):
    pr = hist.pr_do_commit
    assert pr[oid("c0")] is None  # direto na main
    assert pr[oid("c1")] == pr[oid("a10")] == 10
    assert pr[oid("c3")] == 11  # também está no #15, que não foi mergeado
    assert pr[oid("b1")] == pr[oid("a11")] == 11
    assert pr[oid("e0")] is None
    assert oid("e5") not in pr  # depois do momento pedido


def test_tipo_dos_merges(hist):
    merges = {c.curto: hg.tipo_merge(c, hist.prs) for c in hist.commits if c.merge}
    assert merges == {
        "a10a10a": hg.TIPO_MERGE_PR,
        "b1b1b1b": hg.TIPO_MERGE_BRANCH,
        "a11a11a": hg.TIPO_MERGE_PR,
        "a12a12a": hg.TIPO_MERGE_PR,
    }


def test_commits_do_lider_em_prs_de_colegas(hist):
    lista = hg.commits_do_lider_em_prs_de_colegas(hist)
    assert [(pr.numero, c.curto, c.merge) for pr, c in lista] == [
        (11, "c3c3c3c", False),
        (11, "b1b1b1b", True),
    ]


# ---------------------------------------------------------------- contagens


def test_resumo_por_integrante(hist):
    def resumo(login):
        cont = hg.contar(hist.eventos, login)
        return tuple(cont[t] for t, _ in hg.COLUNAS)

    #                 commits merges abertos mergeados mergeou revisões issues
    assert resumo(LIDER) == (3, 4, 3, 1, 3, 3, 1)
    assert resumo(JOAO) == (1, 0, 1, 1, 0, 1, 1)  # a resposta no próprio PR não conta
    assert resumo(ALISSON) == (1, 0, 1, 1, 0, 1, 1)
    assert resumo(hg.AUTOMACAO) == (0, 0, 1, 0, 0, 1, 0)
    assert resumo(hg.OUTROS) == (1, 0, 0, 0, 0, 0, 0)
    assert hg.categorias(hist.eventos) == [LIDER, JOAO, ALISSON, hg.AUTOMACAO, hg.OUTROS]
    total = Counter(e.tipo for e in hist.eventos)
    assert total[hg.COMMIT] + total[hg.MERGE] == len(hist.commits) == 10


def test_pontos_das_issues_fechadas_por_responsavel(hist):
    assert hg.pontos_fechados(hist.eventos, LIDER) == 3
    assert hg.pontos_fechados(hist.eventos, JOAO) == 5
    assert hg.pontos_fechados(hist.eventos, JOAO, DIAS[1]) == 0
    assert hg.pontos_fechados(hist.eventos, JOAO, DIAS[2]) == 5


def test_contagem_e_horario_por_dia_em_brasilia(hist):
    assert hist.dias == DIAS
    dia = hg.contar(hist.eventos, LIDER, DIAS[1])
    assert (dia[hg.COMMIT], dia[hg.MERGE], dia[hg.REVISAO], dia[hg.MERGEOU]) == (1, 2, 2, 1)
    assert hg.fmt_horario(hg.janela(hist.eventos, LIDER, DIAS[0])) == "22:28–23:10"
    assert hg.fmt_horario(hg.janela(hist.eventos, ALISSON, DIAS[1])) == "18:23"
    assert hg.fmt_horario(None) == "—"


def test_dias_sem_atividade_entram_no_periodo():
    eventos = [
        hg.Evento(LIDER, datetime(2026, 10, 18, 12, tzinfo=UTC), hg.COMMIT, "a"),
        hg.Evento(LIDER, datetime(2026, 10, 20, 12, tzinfo=UTC), hg.COMMIT, "b"),
    ]
    assert hg.dias_do_periodo(eventos) == list(DIAS)
    assert hg.dias_do_periodo([]) == []


def test_sprint_de_cada_dia(hist):
    sprints = hist.rel.sprints
    assert [hg.sprint_do_dia(d, sprints) for d in DIAS] == [
        "Sprint 1",
        "Sprint 2",
        "após as sprints",
    ]
    assert hg.sprint_do_dia(date(2026, 10, 17), sprints) == "antes das sprints"


def test_divergencia_entre_plano_e_atribuicao(hist):
    assert [(i.numero, p, a) for i, p, a in hg.divergencias(hist)] == [(4, (ALISSON,), (LIDER,))]
    assert hg.planejados_da_issue(hist, 5) == (ALISSON,)  # fora do arquivo: a atribuição


# ---------------------------------------------------------------- Markdown


def test_bloco_de_pontos_bate_com_o_burndown(hist):
    md = "\n".join(hg.bloco_pontos(hist))
    assert "| @cerfdotdev | 2 | 4 | 6 | 3 | 3 |" in md
    assert "| @joaoarenda | 1 | 5 | 5 | 5 | 0 |" in md
    assert "| @Alisson-dutra | 2 | 5 | 3 | 3 | 0 |" in md
    assert "planejada para @Alisson-dutra, atribuída a @cerfdotdev no Project" in md
    por_login = {r.login: r.atribuido for r in hist.rel.por_responsavel}
    assert por_login == {LIDER: 6, JOAO: 5, ALISSON: 3}


def test_blocos_do_relatorio(hist):
    blocos = hg.blocos_relatorio(hist)
    assert set(blocos) >= {"gerado", "tarefas", "diario", "lider", "dailies", "burndown"}
    assert "| @cerfdotdev | Líder técnico | 3 | 4 | 3 | 1 | 3 | 3 | 1 | 3 |" in blocos["resumo"]
    assert "| @joaoarenda | 0 | 1 | 0 | 1 |" in blocos["commits-por-dia"]
    assert "| 19/10 | Sprint 2 | 20:00–22:11 | 1 | 0 | 1 | 1 | 0 | 0 | 0 |" in blocos["diario"]
    assert "API base \\| com barra" in blocos["tarefas"]
    assert "em aberto; atribuída a @cerfdotdev" in blocos["tarefas"]
    assert "(aberto)" in blocos["tarefas"]
    assert (
        "| [#11](" in blocos["lider"]
        and "| **Total** |  | **2** | **0** | **1** | **1** |" in (blocos["lider"])
    )
    assert "0 comentários (aberta)" in blocos["dailies"]
    assert "Nas 5 issues do repositório há 2 comentários no total." in blocos["dailies"]
    assert "Desktop: empacotar: 2 pts, @cerfdotdev, PR [#13](" in blocos["abertas"]
    assert "| **Total** |  | **14** | **0** | **3** | **8** | **3** |" in blocos["burndown"]


def test_historico_completo_sem_emails(hist):
    md = hg.renderizar_historico(hist)
    assert "@" not in md.replace("@cerfdotdev", "").replace("@joaoarenda", "").replace(
        "@Alisson-dutra", ""
    )
    assert "exemplo.com" not in md and "noreply" not in md.replace("e-mail noreply", "")
    assert "| 22:28 | @cerfdotdev | [`c0c0c0c`]" in md and hg.DIRETO_NA_MAIN in md
    assert "| 10:00 | outros | [`e0e0e0e`]" in md
    assert "| Visitante | outros | não identificada | 1 |" in md
    assert "revisor-automatico[bot] (automação) COMMENTED 19/10 21:00" in md
    assert "@joaoarenda COMMENTED 19/10 21:30 (do autor)" in md
    assert "fechado sem merge (19/10 01:30)" in md
    assert "@cerfdotdev 1 + 1 merge" in md
    assert "| merge entre branches | [#11](" in md
    assert "depois do momento pedido" not in md
    assert "## Avisos sobre os dados" in md


def test_atualizar_blocos_so_entre_os_marcadores():
    texto = (
        "antes\n<!-- historico:a -->\nvelho\n<!-- /historico:a -->\nmeio\n"
        "<!-- historico:b -->\n<!-- /historico:b -->\ndepois\n"
    )
    novo, ausentes = hg.atualizar_blocos(texto, {"a": "A1", "b": "B1\n", "c": "C1"})
    assert ausentes == ["c"]
    assert novo == (
        "antes\n<!-- historico:a -->\n\nA1\n\n<!-- /historico:a -->\nmeio\n"
        "<!-- historico:b -->\n\nB1\n\n<!-- /historico:b -->\ndepois\n"
    )
    assert hg.atualizar_blocos(novo, {"a": "A1", "b": "B1"})[0] == novo  # idempotente


def test_resumo_no_terminal(hist):
    texto = hg.resumo_terminal(hist, ["docs/relatorio/historico.md"], ["burndown"])
    assert "@cerfdotdev: 3 commits, 4 merges, 3 prs abertos" in texto
    assert "Commits do líder em PRs de colegas: 1 commits e 1 merges." in texto
    assert "Commits na main sem PR: 2." in texto
    assert "#4: planejada para Alisson-dutra, atribuída a cerfdotdev." in texto
    assert "Marcadores ausentes em relatorio.md: burndown." in texto


# ---------------------------------------------------------------- busca e linha de comando


def test_busca_de_conexao_pagina_ate_o_fim():
    paginas = [
        {"hasNextPage": True, "endCursor": "c1", "nodes": [{"number": 1}]},
        {"hasNextPage": False, "endCursor": None, "nodes": [{"number": 2}]},
    ]
    chamadas = []

    def executar(args):
        chamadas.append(list(args))
        pagina = paginas[len(chamadas) - 1]
        info = {"hasNextPage": pagina["hasNextPage"], "endCursor": pagina["endCursor"]}
        conexao = {"pageInfo": info, "nodes": pagina["nodes"]}
        return json.dumps({"data": {"repository": {"issues": conexao}}})

    nos = hg.buscar_conexao(hg.CONSULTA_ISSUES, "issues", {"porPagina": 1}, executar)
    assert nos == [{"number": 1}, {"number": 2}]
    assert "depois=c1" not in chamadas[0] and "depois=c1" in chamadas[1]
    assert f"repo={hg.REPOSITORIO}" in chamadas[0] and "porPagina=1" in chamadas[0]


@pytest.mark.parametrize(
    ("resposta", "mensagem"),
    [
        ({"errors": [{"message": "sem permissão"}]}, "erro na consulta"),
        ({"data": {"repository": None}}, "não encontrado"),
    ],
)
def test_busca_com_erro(resposta, mensagem):
    with pytest.raises(bd.ErroDados, match=mensagem):
        hg.buscar_conexao(hg.CONSULTA_PRS, "pullRequests", {}, lambda _a: json.dumps(resposta))


def test_buscar_git_le_a_ref_pedida():
    chamadas = []
    log = f"{oid('c0')}\x1f\x1f2026-10-18T22:28:00-03:00\x1fCarlos\x1fl@x\x1finício\x1e\n"

    def executar(args):
        chamadas.append(list(args))
        return f"{oid('c0')}\n" if args[0] == "rev-parse" else log

    dump = hg.buscar_git("origin/main", executar)
    assert dump["ref"] == "origin/main" and dump["oid"] == oid("c0")
    assert dump["commits"][0]["assunto"] == "início"
    assert chamadas[0] == ["rev-parse", "--verify", "origin/main^{commit}"]
    assert chamadas[1] == ["log", f"--format={hg.FORMATO_LOG}", oid("c0")]


def test_main_grava_historico_e_blocos(tmp_path, capsys):
    responsaveis = tmp_path / "responsaveis.json"
    responsaveis.write_text(json.dumps(PLANEJADO), encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / hg.NOME_RELATORIO).write_text(
        "# Relatório\n\n<!-- historico:resumo -->\n<!-- /historico:resumo -->\n\nfim\n",
        encoding="utf-8",
    )
    dump = tmp_path / "copia.json"
    args = ["--entrada", str(DADOS), "--salvar-dump", str(dump), "--agora", "2026-10-20T12:00"]
    args += ["--saida", str(docs), "--responsaveis", str(responsaveis)]
    assert hg.main(args) == 0
    historico = (docs / hg.NOME_HISTORICO).read_text(encoding="utf-8")
    relatorio = (docs / hg.NOME_RELATORIO).read_text(encoding="utf-8")
    assert "Gerado em 20/10/2026 12:00" in historico
    assert relatorio.startswith("# Relatório\n") and relatorio.endswith("fim\n")
    assert "| @cerfdotdev | Líder técnico | 3 |" in relatorio
    assert json.loads(dump.read_text(encoding="utf-8")) == json.loads(DADOS.read_text("utf-8"))
    saida = capsys.readouterr().out
    assert "Marcadores ausentes em relatorio.md: gerado, pontos" in saida


def test_main_com_entrada_invalida(tmp_path, capsys):
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{}", encoding="utf-8")
    assert hg.main(["--entrada", str(ruim), "--saida", str(tmp_path)]) == 1
    assert "historico:" in capsys.readouterr().err


def test_git_ausente(monkeypatch):
    monkeypatch.setattr(hg.shutil, "which", lambda _nome: None)
    with pytest.raises(bd.ErroDados, match="git"):
        hg.executar_git(["log"])
