"""Cálculo, textos e saída do burndown, com um Project pequeno de exemplo (dados/projeto.json)."""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import burndown as bd

DADOS = Path(__file__).parent / "dados" / "projeto.json"
AGORA = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # 20/10 12:00 em Brasília
# Limites das sprints do exemplo, em UTC (meia-noite em Brasília = 03:00 UTC)
FIM_SPRINT_1 = datetime(2026, 10, 19, 3, 0, tzinfo=UTC)
FIM_SPRINT_2 = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)


@pytest.fixture
def bruto():
    return json.loads(DADOS.read_text(encoding="utf-8"))


@pytest.fixture
def sprints(bruto):
    return bd.ler_sprints(bruto["sprints"])


@pytest.fixture
def lidos(bruto):
    return bd.ler_itens(bruto["itens"])


@pytest.fixture
def itens(lidos):
    return lidos[0]


@pytest.fixture
def rel(lidos, sprints):
    itens, avisos = lidos
    return bd.calcular(itens, sprints, AGORA, avisos)


def item(rel, numero):
    return next(i for i in rel.itens if i.numero == numero)


# ---------------------------------------------------------------- leitura


def test_sprints_em_ordem_e_com_limites_na_meia_noite_de_brasilia(sprints):
    assert [s.titulo for s in sprints] == ["Sprint 1", "Sprint 2"]
    assert sprints[0].inicio == datetime(2026, 10, 18, 3, 0, tzinfo=UTC)
    assert sprints[0].fim == FIM_SPRINT_1 == sprints[1].inicio
    assert sprints[1].fim == FIM_SPRINT_2


def test_le_so_issues_e_avisa_o_resto(lidos):
    itens, avisos = lidos
    assert [i.numero for i in itens] == [1, 2, 3, 4, 5, 6, 7]
    assert avisos == [
        "Item ignorado por não ser issue (PullRequest): #9",
        "Item ignorado por não ser issue (DraftIssue): Rascunho",
    ]


def test_campos_da_issue(itens):
    aberta, sem_conclusao, sem_pontos = itens[2], itens[5], itens[6]
    assert aberta.fechada is None and aberta.responsaveis == ("ana", "bia")
    assert aberta.merges == ()  # PR não mergeado não conta
    assert sem_conclusao.fechada is not None and not sem_conclusao.concluida
    assert sem_pontos.pontos is None and sem_pontos.peso == 0
    assert sem_pontos.sprint_id is None
    assert itens[3].merges == (bd.Merge(11, datetime(2026, 10, 19, 20, 0, tzinfo=UTC)),)


def test_issue_aberta_ignora_closed_at_antigo(bruto):
    no = bruto["itens"][2]
    no["content"]["closedAt"] = "2026-10-19T00:00:00Z"  # reaberta depois
    (lida,), _ = bd.ler_itens([no])
    assert lida.fechada is None


# ---------------------------------------------------------------- cálculo


def test_serie_soma_criacoes_e_desconta_fechamentos(itens):
    serie = bd.serie_burndown(itens, AGORA)
    valores = [(p.momento.strftime("%d %H:%M"), p.escopo, p.restante) for p in serie]
    assert valores == [
        ("18 13:00", 10, 10),
        ("18 13:01", 18, 18),
        ("18 13:02", 19, 19),
        ("18 13:03", 19, 19),
        ("19 01:00", 19, 16),
        ("19 05:00", 19, 11),
        ("19 15:00", 18, 10),  # não planejada: sai do escopo, não é concluída
        ("20 12:00", 18, 2),
        ("20 13:00", 21, 5),  # escopo adicionado
    ]


def test_serie_para_no_momento_pedido(itens):
    serie = bd.serie_burndown(itens, FIM_SPRINT_2)
    assert serie[-1].momento < FIM_SPRINT_2
    assert (serie[-1].escopo, serie[-1].restante) == (18, 10)


def test_escopo_planejado_e_adicionado(rel):
    assert rel.corte == FIM_SPRINT_1
    assert rel.planejado == 19
    assert [i.numero for i in rel.adicionados] == [5]
    assert (rel.escopo, rel.concluido, rel.restante) == (21, 16, 5)


def test_resumo_por_sprint(rel):
    s1, s2, sem = rel.por_sprint
    assert (s1.titulo, s1.planejado, s1.adicionado, s1.no_prazo, s1.depois, s1.em_aberto) == (
        "Sprint 1",
        8,
        0,
        3,
        5,
        0,
    )
    assert (s2.planejado, s2.adicionado, s2.no_prazo, s2.depois, s2.em_aberto) == (11, 3, 0, 8, 5)
    assert s2.sem_conclusao == 1
    assert sem.titulo == bd.SEM_SPRINT and sem.sprint is None
    for r in rel.por_sprint:
        assert r.planejado + r.adicionado == r.no_prazo + r.depois + r.em_aberto + r.sem_conclusao


def test_resumo_por_responsavel_divide_pontos_compartilhados(rel):
    por_login = {r.login: (r.atribuido, r.concluido, r.no_prazo) for r in rel.por_responsavel}
    assert por_login == {
        "bia": (14, 13, 0),
        "ana": (4, 3, 3),
        bd.SEM_RESPONSAVEL: (4, 0, 0),
    }
    assert [r.login for r in rel.por_responsavel][0] == "bia"  # mais concluído primeiro
    assert sum(r.atribuido for r in rel.por_responsavel) == rel.escopo + 1  # + a não planejada


def test_fechamento_tardio_so_com_merge_dentro_da_sprint(rel):
    assert [(t.item.numero, t.merge.pr, t.sprint.titulo) for t in rel.tardios] == [
        (4, 11, "Sprint 2")
    ]


def test_avisos_sobre_os_dados(rel):
    assert rel.avisos[2:] == (
        "#5 aberta, mas com Status Done",
        "#7 sem Pontos (contada como 0)",
        "#7 sem Sprint",
    )


def test_status_fechada_sem_done_e_sprint_inexistente(itens, sprints):
    fechada = itens[0]
    avisos = bd.verificar_dados(
        [bd.Item(**{**fechada.__dict__, "status": "In Review", "sprint_id": "velha"})], sprints
    )
    assert avisos == [
        "#1 numa Sprint que não existe mais no Project",
        "#1 fechada, mas com Status In Review",
    ]


def test_sem_sprints_e_erro(itens):
    with pytest.raises(bd.ErroDados):
        bd.calcular(itens, [], AGORA)


def test_inicio_visivel_pula_so_a_rajada_de_cadastro(itens):
    serie = bd.serie_burndown(itens, AGORA)
    assert bd.inicio_visivel(serie) == 3  # 13:00 a 13:03, só criações
    assert bd.inicio_visivel(serie, timedelta(minutes=1)) == 1
    fechada_logo = [bd.Ponto(serie[0].momento, 5, 5), bd.Ponto(serie[1].momento, 5, 2)]
    assert bd.inicio_visivel(fechada_logo) == 0


# ---------------------------------------------------------------- textos


@pytest.mark.parametrize(("valor", "texto"), [(3.0, "3"), (0, "0"), (2.5, "2,5"), (1 / 3, "0,3")])
def test_fmt_pts(valor, texto):
    assert bd.fmt_pts(valor) == texto


@pytest.mark.parametrize(
    ("delta", "texto"),
    [
        (timedelta(minutes=47), "47 min"),
        (timedelta(hours=9, minutes=3), "9 h 03 min"),
        (timedelta(days=1, hours=10, minutes=22), "1 d 10 h"),
    ],
)
def test_fmt_duracao(delta, texto):
    assert bd.fmt_duracao(delta) == texto


def test_juntar():
    assert bd.juntar([]) == ""
    assert bd.juntar(["#1"]) == "#1"
    assert bd.juntar(["#1", "#2", "#3"]) == "#1, #2 e #3"


def test_horarios_em_brasilia():
    momento = datetime(2026, 10, 19, 1, 30, tzinfo=UTC)
    assert bd.fmt_momento(momento) == "18/10 22:30"
    assert bd.fmt_intervalo(momento, momento + timedelta(minutes=3)) == "18/10 22:30–22:33"
    assert bd.fmt_intervalo(momento, momento) == "18/10 22:30"
    assert bd.fmt_intervalo(momento, momento + timedelta(hours=3)) == "18/10 22:30 a 19/10 01:30"


def test_fuso_reserva_sem_base_de_fusos(monkeypatch):
    def sem_base(nome):
        raise bd.ZoneInfoNotFoundError(nome)

    monkeypatch.setattr(bd, "ZoneInfo", sem_base)
    fuso = bd.obter_fuso()
    assert fuso.utcoffset(None) == timedelta(hours=-3)
    assert isinstance(fuso, timezone)


def test_notas_explicam_regras_e_casos(rel):
    texto = "\n".join(bd.notas(rel))
    assert "Concluído = issue fechada (closedAt)" in texto
    assert "Planejado: 19 pts em 6 issues criadas até o fim da Sprint 1" in texto
    assert "18/10 10:00–10:03" in texto and "a linha real começa nesse cadastro" in texto
    assert "Escopo adicionado depois: +3 pts (#5, criadas em 20/10)" in texto
    assert "#4 (PR #11 em 19/10 17:00)" in texto


def test_situacao_de_cada_issue(rel):
    assert bd.situacao(item(rel, 1), rel) == "no prazo"
    assert bd.situacao(item(rel, 2), rel) == "2 h 00 min após o fim da sprint"
    assert bd.situacao(item(rel, 4), rel).endswith("PR #11 mergeado em 19/10 17:00")
    assert bd.situacao(item(rel, 5), rel) == "em aberto; adicionada após o planejamento"
    assert bd.situacao(item(rel, 6), rel) == "fechada sem conclusão (NOT_PLANNED)"


# ---------------------------------------------------------------- saída


def test_escala_y():
    assert bd.passo_y(110) == 20
    assert bd.teto_y(110) == 120
    assert bd.teto_y(120) == 140  # sempre com folga acima do maior valor
    assert bd.teto_y(0) == 1


def test_marcas_x_em_horas_cheias_locais(sprints):
    marcas = bd.marcas_x(sprints[0].inicio, AGORA)
    assert [m.strftime("%d %Hh") for m in marcas[:3]] == ["18 00h", "18 06h", "18 12h"]
    assert len(marcas) <= bd.MAX_MARCAS_X


def test_caminho_em_degraus():
    assert bd.caminho_degraus([(0, 10), (5, 4)], 9) == "M0.0,10.0H5.0V4.0H9.0"


def test_afastar_rotulos():
    assert bd.afastar_rotulos([100, 95], 14) == [109, 95]


def test_agrupar_adicoes_proximas(itens):
    base = itens[4]
    longe = bd.Item(**{**base.__dict__, "numero": 8, "criada": base.criada + timedelta(hours=5)})
    perto = bd.Item(**{**base.__dict__, "numero": 9, "criada": base.criada + timedelta(hours=1)})
    grupos = bd.agrupar_adicoes([longe, base, perto])
    assert [[i.numero for i in g] for g in grupos] == [[5, 9], [8]]


def test_svg_valido_com_linhas_e_rotulos(rel):
    svg = bd.renderizar_svg(rel)
    raiz = ET.fromstring(svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    textos = [t.text for t in raiz.iterfind(".//s:text", ns)]
    assert "Sprint 1 · 18/10" in textos and "Sprint 2 · 19/10" in textos
    assert "+3 pts: #5 (20/10 10:00)" in textos
    assert "5 restantes" in textos and "21 no escopo" in textos
    assert any(t.startswith("backlog cadastrado (18/10 10:00–10:03)") for t in textos)
    assert len(raiz.findall("s:path", ns)) == 2  # escopo e restante
    legenda, ideal = raiz.findall("s:line[@stroke-dasharray]", ns)
    base = bd.TOPO_GRAFICO + bd.ALTURA_GRAFICO
    topo = bd.teto_y(rel.escopo)
    assert float(ideal.get("x1")) == bd.MARGEM_ESQ and float(ideal.get("y2")) == base
    assert float(ideal.get("y1")) == pytest.approx(base - 19 / topo * bd.ALTURA_GRAFICO, abs=0.1)
    assert raiz.find("s:rect", ns).get("fill") == bd.COR_FUNDO  # fundo explícito


def test_markdown_com_tabelas_e_comando(rel):
    md = bd.renderizar_md(rel)
    assert f"`{bd.COMANDO}`" in md and "20/10/2026 12:00" in md
    assert "| Sprint 1 | 18/10 | 8 | 0 | 3 | 5 | 0 | 0 |" in md
    assert "| Sprint 2 | 19/10 | 11 | 3 | 0 | 8 | 5 | 1 |" in md
    assert "| **Total** |  | **19** | **3** | **3** | **13** | **5** | **1** |" in md
    assert "| @bia | 14 | 13 | 0 |" in md
    assert "duas horas depois do fim \\| com barra" in md
    assert "## Avisos sobre os dados" in md


def test_resumo_no_terminal(rel):
    texto = bd.resumo_terminal(rel, [Path("docs/burndown.svg")])
    assert "Escopo: 21 pts (19 planejados + 3 adicionados). Concluídos: 16. Restantes: 5." in texto
    assert "Sprint 2: 11 planejados + 3 adicionados; 0 concluídos na sprint" in texto


# ---------------------------------------------------------------- busca e linha de comando


def test_busca_pagina_ate_o_fim(bruto):
    nos = bruto["itens"]
    paginas = [
        {
            "data": {
                "user": {
                    "projectV2": {
                        "sprint": {"configuration": bruto["sprints"]},
                        "items": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                            "nodes": nos[:4],
                        },
                    }
                }
            }
        },
        {
            "data": {
                "user": {
                    "projectV2": {
                        "sprint": {"configuration": bruto["sprints"]},
                        "items": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": nos[4:],
                        },
                    }
                }
            }
        },
    ]
    chamadas = []

    def executar(args):
        chamadas.append(list(args))
        return json.dumps(paginas[len(chamadas) - 1])

    assert bd.buscar_projeto(executar) == bruto
    assert "depois=c1" not in chamadas[0] and "depois=c1" in chamadas[1]
    assert "numero=12" in chamadas[0] and "campoPontos=Pontos" in chamadas[0]


@pytest.mark.parametrize(
    ("resposta", "mensagem"),
    [
        ({"errors": [{"message": "sem permissão"}]}, "erro na consulta"),
        ({"data": {"user": {"projectV2": None}}}, "não encontrado"),
        ({"data": {"user": {"projectV2": {"sprint": {}}}}}, "campo de iteração"),
    ],
)
def test_busca_com_erro(resposta, mensagem):
    with pytest.raises(bd.ErroDados, match=mensagem):
        bd.buscar_projeto(lambda _args: json.dumps(resposta))


def test_main_grava_arquivos_a_partir_do_dump(tmp_path, capsys):
    dump = tmp_path / "copia.json"
    codigo = bd.main(
        [
            "--entrada",
            str(DADOS),
            "--salvar-dump",
            str(dump),
            "--agora",
            "2026-10-20T12:00",
            "--saida",
            str(tmp_path / "docs"),
        ]
    )
    assert codigo == 0
    svg = (tmp_path / "docs" / bd.NOME_SVG).read_text(encoding="utf-8")
    md = (tmp_path / "docs" / bd.NOME_MD).read_text(encoding="utf-8")
    ET.fromstring(svg)
    assert "20/10 12:00" in svg and f"]({bd.NOME_SVG})" in md
    assert json.loads(dump.read_text(encoding="utf-8")) == json.loads(DADOS.read_text("utf-8"))
    assert "Restantes: 5." in capsys.readouterr().out


def test_main_com_entrada_invalida(tmp_path, capsys):
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{}", encoding="utf-8")
    assert bd.main(["--entrada", str(ruim), "--saida", str(tmp_path)]) == 1
    assert "burndown:" in capsys.readouterr().err


def test_gh_ausente(monkeypatch):
    monkeypatch.setattr(bd.shutil, "which", lambda _nome: None)
    with pytest.raises(bd.ErroDados, match="gh"):
        bd.executar_gh(["api"])
