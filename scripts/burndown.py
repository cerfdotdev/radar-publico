"""Gera o burndown das sprints a partir das issues do GitHub Project "Radar Público".

Busca as issues do Project (campos Pontos, Sprint e Status) com o `gh` já autenticado e grava:

- `docs/burndown.svg`: pontos restantes ao longo do tempo, com a linha ideal, o escopo total,
  os limites das sprints e as datas reais de fechamento (horário de Brasília);
- `docs/burndown.md`: tabelas de pontos por sprint e por responsável, notas e a lista de issues.

Uso, a partir da raiz do repositório (só biblioteca padrão; precisa do `gh` com escopo `project`):

    python3 scripts/burndown.py                           # busca no Project e grava em docs/
    python3 scripts/burndown.py --salvar-dump dados.json  # também guarda os dados buscados
    python3 scripts/burndown.py --entrada dados.json      # usa um dump salvo, sem rede
    python3 scripts/burndown.py --agora 2026-10-20T15:00:00-03:00

Regras usadas no cálculo:

- Concluído é a issue fechada (`closedAt`), não o merge do PR. Quando o PR foi mergeado dentro
  da sprint e a issue só foi fechada depois, o script avisa, mas não muda a data.
- Escopo planejado são as issues criadas até o fim da primeira sprint; as criadas depois entram
  como escopo adicionado. A linha real começa quando o backlog foi cadastrado no Project.
- Issue fechada como "não planejada" ou duplicada sai do escopo e não conta como concluída.
- Vale o estado atual de cada issue: uma issue reaberta conta como aberta desde sempre.

Testes e lint (dentro de `scripts/`, com as ferramentas de `.github/ci/requirements.txt`):

    python -m pytest
    ruff check burndown.py tests && ruff format --check burndown.py tests
"""

import argparse
import html
import json
import math
import shutil
import subprocess  # nosec B404
import sys
import textwrap
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Project de origem
DONO = "cerfdotdev"
NUMERO_PROJETO = 12
CAMPO_PONTOS = "Pontos"
CAMPO_SPRINT = "Sprint"
CAMPO_STATUS = "Status"
STATUS_CONCLUIDO = "Done"
ITENS_POR_PAGINA = 100
MAX_RESPONSAVEIS = 10
MAX_PRS_POR_ISSUE = 10
# Fechadas com esses motivos saem do escopo em vez de contar como concluídas
MOTIVOS_SEM_CONCLUSAO = frozenset({"NOT_PLANNED", "DUPLICATE"})
ESTADO_ABERTA = "OPEN"

# Fuso dos horários. O Brasil não tem horário de verão desde 2019, então UTC-3 serve de
# reserva quando o sistema não tem a base de fusos (Windows sem o pacote tzdata).
NOME_FUSO = "America/Sao_Paulo"
DESLOCAMENTO_RESERVA = timedelta(hours=-3)

RAIZ = Path(__file__).resolve().parent.parent
DIR_SAIDA = RAIZ / "docs"
NOME_SVG = "burndown.svg"
NOME_MD = "burndown.md"
COMANDO = "python3 scripts/burndown.py"
SEM_RESPONSAVEL = "(sem responsável)"
SEM_SPRINT = "Sem sprint"

# Layout do SVG (px)
LARGURA = 960
MARGEM_ESQ = 64
MARGEM_DIR = 132
MARGEM_LATERAL_TEXTO = 24
Y_TITULO = 34
Y_SUBTITULO = 56
Y_LEGENDA = 82
TOPO_GRAFICO = 120
ALTURA_GRAFICO = 330
Y_ROTULO_FAIXA = TOPO_GRAFICO - 8
DY_HORA = 18
DY_DATA = 34
DY_NOTAS = 66
ALTURA_LINHA_NOTA = 18
MARGEM_INFERIOR = 14
RAIO_CANTO = 8
RAIO_PONTO = 4
ANEL_PONTO = 2
LARGURA_LINHA_REAL = 2.5
LARGURA_LINHA = 1.5
TRACO_IDEAL = "6 4"
TAM_TITULO = 18
TAM_SUBTITULO = 13
TAM_TEXTO = 12
TAM_EIXO = 11
LARGURA_AMOSTRA_LEGENDA = 22
ESPACO_LEGENDA = 28
LARGURA_CARACTERE = 6.6  # média aproximada da fonte sans de 12 px
CARACTERES_POR_NOTA = 128  # cabe na largura mesmo com fontes mais largas (DejaVu Sans)
HALO = 4  # contorno das anotações, na cor do fundo
AFASTAMENTO_ROTULO = 8
Y_AMOSTRA_LEGENDA = Y_LEGENDA - 4  # traço da legenda na altura do meio do texto
CENTRO_TEXTO = 1 / 3  # fração do tamanho da fonte que centraliza o texto na vertical
MEIO_PIXEL = 0.5  # borda do cartão alinhada à grade de pixels
NEGRITO = "600"
SEPARACAO_MIN_ROTULOS = 14
DIST_MIN_MARCA_BORDA = 24
MAX_DIVISOES_Y = 8
PASSOS_Y = (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)
PASSOS_X_HORAS = (1, 2, 3, 6, 12, 24, 48, 96)
MAX_MARCAS_X = 12
HORAS_POR_DIA = 24
MINUTOS_POR_HORA = 60
SEGUNDOS_POR_HORA = 3600
JANELA_ESCOPO = timedelta(hours=2)  # inclusões de escopo próximas viram um só rótulo
JANELA_CADASTRO = timedelta(hours=1)  # rajada inicial de criações desenhada como um ponto
FONTE = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# Cores: cartão claro com fundo explícito, legível nos temas claro e escuro do GitHub.
# Azul e laranja passam no validador de paleta (daltonismo e contraste) sobre o branco.
COR_FUNDO = "#ffffff"
COR_BORDA = "#d0d7de"
COR_TEXTO = "#1f2328"
COR_TEXTO_2 = "#59636e"
COR_GRADE = "#eaeef2"
COR_EIXO = "#8c959f"
COR_FAIXA_DEPOIS = "#f6f8fa"
COR_REAL = "#2a78d6"
COR_ESCOPO = "#eb6834"
COR_IDEAL = "#6e7781"

CONSULTA = """
query($dono: String!, $numero: Int!, $depois: String, $campoPontos: String!,
      $campoSprint: String!, $campoStatus: String!, $porPagina: Int!,
      $maxResponsaveis: Int!, $maxPrs: Int!) {
  user(login: $dono) {
    projectV2(number: $numero) {
      sprint: field(name: $campoSprint) {
        ... on ProjectV2IterationField {
          configuration {
            iterations { id title startDate duration }
            completedIterations { id title startDate duration }
          }
        }
      }
      items(first: $porPagina, after: $depois) {
        pageInfo { hasNextPage endCursor }
        nodes {
          content {
            __typename
            ... on Issue {
              number title state stateReason createdAt closedAt
              assignees(first: $maxResponsaveis) { nodes { login } }
              closedByPullRequestsReferences(first: $maxPrs, includeClosedPrs: true) {
                nodes { number mergedAt }
              }
            }
            ... on PullRequest { number title }
            ... on DraftIssue { title }
          }
          pontos: fieldValueByName(name: $campoPontos) {
            ... on ProjectV2ItemFieldNumberValue { number }
          }
          sprint: fieldValueByName(name: $campoSprint) {
            ... on ProjectV2ItemFieldIterationValue { iterationId }
          }
          status: fieldValueByName(name: $campoStatus) {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
      }
    }
  }
}
"""


class ErroDados(Exception):
    """Dados do Project ausentes ou num formato inesperado."""


@dataclass(frozen=True)
class Sprint:
    id: str
    titulo: str
    inicio: datetime
    fim: datetime


@dataclass(frozen=True)
class Merge:
    pr: int
    momento: datetime


@dataclass(frozen=True)
class Item:
    numero: int
    titulo: str
    pontos: float | None
    sprint_id: str | None
    status: str | None
    criada: datetime
    fechada: datetime | None
    concluida: bool
    motivo: str | None
    responsaveis: tuple[str, ...]
    merges: tuple[Merge, ...]

    @property
    def peso(self) -> float:
        return self.pontos or 0.0


@dataclass(frozen=True)
class Ponto:
    momento: datetime
    escopo: float
    restante: float


@dataclass(frozen=True)
class ResumoSprint:
    titulo: str
    sprint: Sprint | None
    planejado: float
    adicionado: float
    no_prazo: float
    depois: float
    em_aberto: float
    sem_conclusao: float


@dataclass(frozen=True)
class ResumoResponsavel:
    login: str
    atribuido: float
    concluido: float
    no_prazo: float


@dataclass(frozen=True)
class FechamentoTardio:
    item: Item
    sprint: Sprint
    merge: Merge


@dataclass(frozen=True)
class Relatorio:
    sprints: tuple[Sprint, ...]
    itens: tuple[Item, ...]
    agora: datetime
    corte: datetime
    serie: tuple[Ponto, ...]
    planejado: float
    adicionados: tuple[Item, ...]
    por_sprint: tuple[ResumoSprint, ...]
    por_responsavel: tuple[ResumoResponsavel, ...]
    tardios: tuple[FechamentoTardio, ...]
    avisos: tuple[str, ...]

    @property
    def escopo(self) -> float:
        return self.serie[-1].escopo if self.serie else 0.0

    @property
    def restante(self) -> float:
        return self.serie[-1].restante if self.serie else 0.0

    @property
    def concluido(self) -> float:
        return sum(i.peso for i in self.itens if i.fechada and i.concluida)


# ---------------------------------------------------------------- leitura dos dados


def obter_fuso() -> tzinfo:
    try:
        return ZoneInfo(NOME_FUSO)
    except ZoneInfoNotFoundError:
        return timezone(DESLOCAMENTO_RESERVA, NOME_FUSO)


FUSO = obter_fuso()


def ler_momento(texto: str | None) -> datetime | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto).astimezone(UTC)


def ler_sprints(configuracao: dict, fuso: tzinfo = FUSO) -> list[Sprint]:
    """Iterações (abertas e encerradas) em ordem de início; cada uma começa à 0h local."""
    brutas = (configuracao.get("iterations") or []) + (
        configuracao.get("completedIterations") or []
    )
    sprints = []
    for it in brutas:
        inicio = datetime.combine(date.fromisoformat(it["startDate"]), time(), tzinfo=fuso)
        fim = inicio + timedelta(days=it["duration"])
        sprints.append(Sprint(it["id"], it["title"], inicio, fim))
    return sorted(sprints, key=lambda s: s.inicio)


def ler_itens(nos: Iterable[dict]) -> tuple[list[Item], list[str]]:
    """Converte os itens do Project; o que não é issue fica de fora, com aviso."""
    itens, avisos = [], []
    for no in nos:
        conteudo = no.get("content") or {}
        tipo = conteudo.get("__typename")
        if tipo != "Issue":
            nome = f"#{conteudo['number']}" if "number" in conteudo else conteudo.get("title")
            avisos.append(f"Item ignorado por não ser issue ({tipo}): {nome}")
            continue
        fechada = ler_momento(conteudo.get("closedAt"))
        if conteudo.get("state") == ESTADO_ABERTA:
            fechada = None
        motivo = conteudo.get("stateReason")
        prs = (conteudo.get("closedByPullRequestsReferences") or {}).get("nodes", [])
        mergeados = [
            Merge(pr["number"], ler_momento(pr["mergedAt"])) for pr in prs if pr["mergedAt"]
        ]
        merges = tuple(sorted(mergeados, key=lambda m: m.momento))
        itens.append(
            Item(
                numero=conteudo["number"],
                titulo=conteudo["title"],
                pontos=(no.get("pontos") or {}).get("number"),
                sprint_id=(no.get("sprint") or {}).get("iterationId"),
                status=(no.get("status") or {}).get("name"),
                criada=ler_momento(conteudo["createdAt"]),
                fechada=fechada,
                concluida=fechada is not None and motivo not in MOTIVOS_SEM_CONCLUSAO,
                motivo=motivo,
                responsaveis=tuple(a["login"] for a in conteudo["assignees"]["nodes"]),
                merges=merges,
            )
        )
    return sorted(itens, key=lambda i: i.numero), avisos


# ---------------------------------------------------------------- cálculo


def serie_burndown(itens: Iterable[Item], ate: datetime) -> list[Ponto]:
    """Escopo total e pontos restantes depois de cada evento (criação ou fechamento)."""
    deltas: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for item in itens:
        if item.criada > ate:
            continue
        deltas[item.criada][0] += item.peso
        deltas[item.criada][1] += item.peso
        if item.fechada and item.fechada <= ate:
            if not item.concluida:
                deltas[item.fechada][0] -= item.peso
            deltas[item.fechada][1] -= item.peso
    serie, escopo, restante = [], 0.0, 0.0
    for momento in sorted(deltas):
        escopo += deltas[momento][0]
        restante += deltas[momento][1]
        serie.append(Ponto(momento, escopo, restante))
    return serie


def separar_escopo(itens: Iterable[Item], corte: datetime) -> tuple[list[Item], list[Item]]:
    """(planejados, adicionados): criados até o corte e depois dele."""
    planejados, adicionados = [], []
    for item in itens:
        (planejados if item.criada <= corte else adicionados).append(item)
    return planejados, adicionados


def resumir_sprints(
    itens: Iterable[Item], sprints: Sequence[Sprint], corte: datetime
) -> list[ResumoSprint]:
    por_id = {s.id: s for s in sprints}
    grupos: dict[str | None, list[Item]] = defaultdict(list)
    for item in itens:
        grupos[item.sprint_id if item.sprint_id in por_id else None].append(item)
    chaves = [s.id for s in sprints if s.id in grupos] + ([None] if None in grupos else [])
    resumos = []
    for chave in chaves:
        sprint = por_id.get(chave)
        grupo = grupos[chave]
        concluidos = [i for i in grupo if i.fechada and i.concluida]
        resumos.append(
            ResumoSprint(
                titulo=sprint.titulo if sprint else SEM_SPRINT,
                sprint=sprint,
                planejado=sum(i.peso for i in grupo if i.criada <= corte),
                adicionado=sum(i.peso for i in grupo if i.criada > corte),
                no_prazo=sum(i.peso for i in concluidos if sprint and i.fechada < sprint.fim),
                depois=sum(i.peso for i in concluidos if not sprint or i.fechada >= sprint.fim),
                em_aberto=sum(i.peso for i in grupo if not i.fechada),
                sem_conclusao=sum(i.peso for i in grupo if i.fechada and not i.concluida),
            )
        )
    return resumos


def resumir_responsaveis(
    itens: Iterable[Item], sprints: Sequence[Sprint]
) -> list[ResumoResponsavel]:
    """Pontos por responsável; issue com vários responsáveis divide os pontos igualmente."""
    por_id = {s.id: s for s in sprints}
    soma: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for item in itens:
        logins = item.responsaveis or (SEM_RESPONSAVEL,)
        parte = item.peso / len(logins)
        sprint = por_id.get(item.sprint_id)
        for login in logins:
            soma[login][0] += parte
            if item.fechada and item.concluida:
                soma[login][1] += parte
                if sprint and item.fechada < sprint.fim:
                    soma[login][2] += parte
    resumos = [ResumoResponsavel(login, *valores) for login, valores in soma.items()]
    return sorted(resumos, key=lambda r: (-r.concluido, r.login.lower()))


def fechamentos_tardios(itens: Iterable[Item], sprints: Sequence[Sprint]) -> list[FechamentoTardio]:
    """Issues fechadas depois do fim da sprint cujo PR já tinha sido mergeado dentro dela."""
    por_id = {s.id: s for s in sprints}
    tardios = []
    for item in itens:
        sprint = por_id.get(item.sprint_id)
        if not (sprint and item.fechada and item.concluida and item.merges):
            continue
        primeiro = item.merges[0]
        if item.fechada >= sprint.fim and primeiro.momento < sprint.fim:
            tardios.append(FechamentoTardio(item, sprint, primeiro))
    return tardios


def verificar_dados(itens: Iterable[Item], sprints: Sequence[Sprint]) -> list[str]:
    ids = {s.id for s in sprints}
    avisos = []
    for item in itens:
        ref = f"#{item.numero}"
        if item.pontos is None:
            avisos.append(f"{ref} sem {CAMPO_PONTOS} (contada como 0)")
        if item.sprint_id is None:
            avisos.append(f"{ref} sem {CAMPO_SPRINT}")
        elif item.sprint_id not in ids:
            avisos.append(f"{ref} numa {CAMPO_SPRINT} que não existe mais no Project")
        if item.status is None:
            avisos.append(f"{ref} sem {CAMPO_STATUS}")
        elif item.fechada and item.status != STATUS_CONCLUIDO:
            avisos.append(f"{ref} fechada, mas com {CAMPO_STATUS} {item.status}")
        elif not item.fechada and item.status == STATUS_CONCLUIDO:
            avisos.append(f"{ref} aberta, mas com {CAMPO_STATUS} {STATUS_CONCLUIDO}")
    return avisos


def calcular(
    itens: Sequence[Item],
    sprints: Sequence[Sprint],
    agora: datetime,
    avisos_leitura: Sequence[str] = (),
) -> Relatorio:
    if not sprints:
        raise ErroDados(f"o campo {CAMPO_SPRINT} não tem iterações")
    corte = sprints[0].fim
    planejados, adicionados = separar_escopo(itens, corte)
    return Relatorio(
        sprints=tuple(sprints),
        itens=tuple(itens),
        agora=agora,
        corte=corte,
        serie=tuple(serie_burndown(itens, agora)),
        planejado=sum(i.peso for i in planejados),
        adicionados=tuple(i for i in adicionados if i.criada <= agora),
        por_sprint=tuple(resumir_sprints(itens, sprints, corte)),
        por_responsavel=tuple(resumir_responsaveis(itens, sprints)),
        tardios=tuple(fechamentos_tardios(itens, sprints)),
        avisos=tuple(avisos_leitura) + tuple(verificar_dados(itens, sprints)),
    )


# ---------------------------------------------------------------- textos


def fmt_pts(valor: float) -> str:
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:.1f}".replace(".", ",")


def local(momento: datetime) -> datetime:
    return momento.astimezone(FUSO)


def fmt_dia(momento: datetime) -> str:
    return local(momento).strftime("%d/%m")


def fmt_hora(momento: datetime) -> str:
    return local(momento).strftime("%H:%M")


def fmt_momento(momento: datetime) -> str:
    return local(momento).strftime("%d/%m %H:%M")


def fmt_intervalo(inicio: datetime, fim: datetime) -> str:
    if fmt_dia(inicio) == fmt_dia(fim):
        if fmt_hora(inicio) == fmt_hora(fim):
            return fmt_momento(inicio)
        return f"{fmt_momento(inicio)}–{fmt_hora(fim)}"
    return f"{fmt_momento(inicio)} a {fmt_momento(fim)}"


def fmt_duracao(delta: timedelta) -> str:
    minutos = int(delta.total_seconds() // (SEGUNDOS_POR_HORA // MINUTOS_POR_HORA))
    dias, resto = divmod(minutos, HORAS_POR_DIA * MINUTOS_POR_HORA)
    horas, minutos = divmod(resto, MINUTOS_POR_HORA)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min"


def juntar(partes: Sequence[str]) -> str:
    if len(partes) <= 1:
        return "".join(partes)
    return f"{', '.join(partes[:-1])} e {partes[-1]}"


def refs(itens: Iterable[Item]) -> str:
    return juntar([f"#{i.numero}" for i in itens])


def periodo_sprint(sprint: Sprint) -> str:
    ultimo_dia = sprint.fim - timedelta(days=1)
    if fmt_dia(sprint.inicio) == fmt_dia(ultimo_dia):
        return fmt_dia(sprint.inicio)
    return f"{fmt_dia(sprint.inicio)} a {fmt_dia(ultimo_dia)}"


def notas(rel: Relatorio) -> list[str]:
    """Notas que acompanham o gráfico, a tabela e o resumo no terminal."""
    primeira, ultima = rel.sprints[0], rel.sprints[-1]
    planejados = [i for i in rel.itens if i.criada <= rel.corte]
    datas = [f"{s.titulo} em {periodo_sprint(s)}" for s in rel.sprints]
    linhas = [
        "Concluído = issue fechada (closedAt), não o merge do PR. "
        f"Sprints: {juntar(datas)}; fim planejado em {fmt_momento(ultima.fim)}."
    ]
    if planejados:
        cadastro = fmt_intervalo(
            min(i.criada for i in planejados), max(i.criada for i in planejados)
        )
        linha = (
            f"Planejado: {fmt_pts(rel.planejado)} pts em {len(planejados)} issues criadas "
            f"até o fim da {primeira.titulo} (cadastradas no Project em {cadastro})"
        )
        if min(i.criada for i in planejados) > primeira.inicio:
            linha += "; a linha real começa nesse cadastro"
        linhas.append(linha + ".")
    if rel.adicionados:
        pts = sum(i.peso for i in rel.adicionados)
        linhas.append(
            f"Escopo adicionado depois: +{fmt_pts(pts)} pts ({refs(rel.adicionados)}, "
            f"criadas em {juntar(sorted({fmt_dia(i.criada) for i in rel.adicionados}))})."
        )
    if rel.tardios:
        por_pr: dict[int, list[FechamentoTardio]] = defaultdict(list)
        for t in rel.tardios:
            por_pr[t.merge.pr].append(t)
        grupos = [
            f"{refs(t.item for t in ts)} (PR #{pr} em {fmt_momento(ts[0].merge.momento)})"
            for pr, ts in sorted(por_pr.items(), key=lambda kv: kv[1][0].item.numero)
        ]
        pts = sum(t.item.peso for t in rel.tardios)
        dias = juntar(sorted({fmt_dia(t.item.fechada) for t in rel.tardios}))
        linhas.append(
            f"PR mergeado dentro da sprint, issue fechada só depois do fim ({fmt_pts(pts)} pts): "
            f"{'; '.join(grupos)}. Fechadas em {dias}; o gráfico usa o fechamento."
        )
    return linhas


def rodape(rel: Relatorio) -> str:
    gerado = local(rel.agora).strftime("%d/%m/%Y %H:%M")
    return f"Horário de Brasília ({NOME_FUSO}). Gerado em {gerado} por {COMANDO}."


def situacao(item: Item, rel: Relatorio) -> str:
    sprint = next((s for s in rel.sprints if s.id == item.sprint_id), None)
    if not item.fechada:
        partes = ["em aberto"]
    elif not item.concluida:
        partes = [f"fechada sem conclusão ({item.motivo})"]
    elif sprint and item.fechada < sprint.fim:
        partes = ["no prazo"]
    elif sprint:
        partes = [f"{fmt_duracao(item.fechada - sprint.fim)} após o fim da sprint"]
    else:
        partes = ["concluída"]
    if item.criada > rel.corte:
        partes.append("adicionada após o planejamento")
    tardio = next((t for t in rel.tardios if t.item.numero == item.numero), None)
    if tardio:
        partes.append(f"PR #{tardio.merge.pr} mergeado em {fmt_momento(tardio.merge.momento)}")
    return "; ".join(partes)


# ---------------------------------------------------------------- SVG


def passo_y(maximo: float) -> float:
    return next((p for p in PASSOS_Y if maximo / p <= MAX_DIVISOES_Y), PASSOS_Y[-1])


def teto_y(maximo: float) -> float:
    """Topo do eixo y: múltiplo do passo, com folga acima do maior valor."""
    passo = passo_y(maximo)
    return max(passo, (math.floor(maximo / passo) + 1) * passo)


def marcas_x(inicio: datetime, fim: datetime) -> list[datetime]:
    """Marcas em horas cheias locais (0h, 6h, ...), no máximo MAX_MARCAS_X."""
    horas = (fim - inicio).total_seconds() / SEGUNDOS_POR_HORA
    passo = next((p for p in PASSOS_X_HORAS if horas / p <= MAX_MARCAS_X), PASSOS_X_HORAS[-1])
    marca = datetime.combine(local(inicio).date(), time(), tzinfo=FUSO)
    marcas = []
    while marca <= fim:
        if marca >= inicio:
            marcas.append(marca)
        marca += timedelta(hours=passo)
    return marcas


def caminho_degraus(pontos: Sequence[tuple[float, float]], x_final: float) -> str:
    """Linha em degraus: cada valor vale até o próximo evento."""
    (x0, y0), *resto = pontos
    partes = [f"M{x0:.1f},{y0:.1f}"]
    partes += [f"H{x:.1f}V{y:.1f}" for x, y in resto]
    partes.append(f"H{x_final:.1f}")
    return "".join(partes)


def afastar_rotulos(ys: Sequence[float], minimo: float) -> list[float]:
    """Empurra rótulos verticais para baixo até ficarem a pelo menos `minimo` px."""
    ordem = sorted(range(len(ys)), key=lambda i: ys[i])
    saida = list(ys)
    for anterior, atual in zip(ordem, ordem[1:], strict=False):
        saida[atual] = max(saida[atual], saida[anterior] + minimo)
    return saida


def agrupar_adicoes(adicionados: Sequence[Item]) -> list[list[Item]]:
    grupos: list[list[Item]] = []
    for item in sorted(adicionados, key=lambda i: i.criada):
        if grupos and item.criada - grupos[-1][-1].criada <= JANELA_ESCOPO:
            grupos[-1].append(item)
        else:
            grupos.append([item])
    return grupos


def inicio_visivel(serie: Sequence[Ponto], janela: timedelta = JANELA_CADASTRO) -> int:
    """Índice do ponto onde a linha começa: o fim da rajada inicial de cadastro.

    Cadastrar o backlog leva alguns minutos; desenhado, esse trecho vira um risco vertical
    saindo do zero. Ele só tem criações (nada fechado ainda), então o valor no fim é exato.
    """
    indice = 0
    for i, ponto in enumerate(serie):
        so_criacoes = math.isclose(ponto.escopo, ponto.restante)
        if ponto.momento - serie[0].momento > janela or not so_criacoes:
            break
        indice = i
    return indice


def texto(x: float, y: float, conteudo: str, **attrs: str | float) -> str:
    extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<text x="{x:.1f}" y="{y:.1f}"{extra}>{html.escape(conteudo)}</text>'


def anotacao(x: float, y: float, conteudo: str, ancora: str = "start") -> str:
    """Texto sobre o gráfico, com contorno da cor do fundo para não brigar com as linhas."""
    return texto(
        x,
        y,
        conteudo,
        font_size=TAM_TEXTO,
        fill=COR_TEXTO_2,
        text_anchor=ancora,
        stroke=COR_FUNDO,
        stroke_width=HALO,
        stroke_linejoin="round",
        paint_order="stroke",
    )


def renderizar_svg(rel: Relatorio) -> str:
    primeira, ultima = rel.sprints[0], rel.sprints[-1]
    inicio = primeira.inicio
    fim_eixo = max(rel.agora, ultima.fim)
    x0, x1 = MARGEM_ESQ, LARGURA - MARGEM_DIR
    y0, y1 = TOPO_GRAFICO, TOPO_GRAFICO + ALTURA_GRAFICO
    maximo = max([rel.planejado] + [p.escopo for p in rel.serie])
    topo = teto_y(maximo)
    span = (fim_eixo - inicio).total_seconds()

    def px(momento: datetime) -> float:
        segundos = (max(momento, inicio) - inicio).total_seconds()
        return x0 + segundos / span * (x1 - x0)

    def py(valor: float) -> float:
        return y1 - valor / topo * (y1 - y0)

    linhas_nota = [
        linha
        for nota in notas(rel) + [rodape(rel)]
        for linha in textwrap.wrap(nota, CARACTERES_POR_NOTA)
    ]
    altura = y1 + DY_NOTAS + len(linhas_nota) * ALTURA_LINHA_NOTA + MARGEM_INFERIOR
    agora_txt = fmt_momento(rel.agora)
    subtitulo = (
        f"Pontos restantes a cada fechamento de issue, de {fmt_momento(inicio)} "
        f"a {agora_txt} (horário de Brasília)"
    )
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" '
        f'viewBox="0 0 {LARGURA} {altura}" font-family="{FONTE}" role="img" '
        'aria-labelledby="titulo descricao">',
        '<title id="titulo">Burndown — Radar Público</title>',
        f'<desc id="descricao">{html.escape(" ".join(notas(rel)))}</desc>',
        f'<rect x="{MEIO_PIXEL}" y="{MEIO_PIXEL}" width="{LARGURA - 2 * MEIO_PIXEL}" '
        f'height="{altura - 2 * MEIO_PIXEL}" rx="{RAIO_CANTO}" '
        f'fill="{COR_FUNDO}" stroke="{COR_BORDA}"/>',
        texto(
            MARGEM_LATERAL_TEXTO,
            Y_TITULO,
            "Burndown — Radar Público",
            font_size=TAM_TITULO,
            font_weight=NEGRITO,
            fill=COR_TEXTO,
        ),
        texto(
            MARGEM_LATERAL_TEXTO, Y_SUBTITULO, subtitulo, font_size=TAM_SUBTITULO, fill=COR_TEXTO_2
        ),
    ]

    # Legenda
    x = MARGEM_LATERAL_TEXTO
    legenda = [
        ("Restante (real)", COR_REAL, LARGURA_LINHA_REAL, None),
        ("Ideal", COR_IDEAL, LARGURA_LINHA, TRACO_IDEAL),
        ("Escopo total", COR_ESCOPO, LARGURA_LINHA, None),
    ]
    for rotulo, cor, largura, traco in legenda:
        tracejado = f' stroke-dasharray="{traco}"' if traco else ""
        s.append(
            f'<line x1="{x}" y1="{Y_AMOSTRA_LEGENDA}" x2="{x + LARGURA_AMOSTRA_LEGENDA}" '
            f'y2="{Y_AMOSTRA_LEGENDA}" stroke="{cor}" stroke-width="{largura}"{tracejado}/>'
        )
        x += LARGURA_AMOSTRA_LEGENDA + AFASTAMENTO_ROTULO
        s.append(texto(x, Y_LEGENDA, rotulo, font_size=TAM_TEXTO, fill=COR_TEXTO))
        x += len(rotulo) * LARGURA_CARACTERE + ESPACO_LEGENDA

    # Faixa depois do fim planejado e limites das sprints
    if fim_eixo > ultima.fim:
        xf = px(ultima.fim)
        s.append(
            f'<rect x="{xf:.1f}" y="{y0}" width="{x1 - xf:.1f}" height="{y1 - y0}" '
            f'fill="{COR_FAIXA_DEPOIS}"/>'
        )
    for valor in range(0, int(topo) + 1, int(passo_y(maximo))):
        y = py(valor)
        s.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{COR_GRADE}"/>')
        s.append(
            texto(
                x0 - AFASTAMENTO_ROTULO,
                y + TAM_EIXO * CENTRO_TEXTO,
                fmt_pts(valor),
                font_size=TAM_EIXO,
                fill=COR_TEXTO_2,
                text_anchor="end",
            )
        )
    s.append(texto(x0, Y_ROTULO_FAIXA, "pontos", font_size=TAM_EIXO, fill=COR_TEXTO_2))
    faixas = [(sp.inicio, sp.fim, f"{sp.titulo} · {periodo_sprint(sp)}") for sp in rel.sprints]
    if fim_eixo > ultima.fim:
        faixas.append((ultima.fim, fim_eixo, "após as sprints"))
    for comeco, final, rotulo in faixas:
        largura = px(final) - px(comeco)
        if len(rotulo) * LARGURA_CARACTERE <= largura:
            s.append(
                texto(
                    (px(comeco) + px(final)) / 2,
                    Y_ROTULO_FAIXA,
                    rotulo,
                    font_size=TAM_TEXTO,
                    fill=COR_TEXTO_2,
                    text_anchor="middle",
                )
            )
    for limite in sorted({sp.inicio for sp in rel.sprints} | {sp.fim for sp in rel.sprints}):
        if limite <= fim_eixo:
            xl = px(limite)
            s.append(f'<line x1="{xl:.1f}" y1="{y0}" x2="{xl:.1f}" y2="{y1}" stroke="{COR_EIXO}"/>')

    # Eixo x
    s.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{COR_EIXO}"/>')
    for marca in marcas_x(inicio, fim_eixo):
        xm = px(marca)
        if x1 - xm < DIST_MIN_MARCA_BORDA:
            continue
        s.append(
            texto(
                xm,
                y1 + DY_HORA,
                marca.strftime("%Hh"),
                font_size=TAM_EIXO,
                fill=COR_TEXTO_2,
                text_anchor="middle",
            )
        )
        if marca.hour == 0:
            s.append(
                texto(
                    xm,
                    y1 + DY_DATA,
                    fmt_dia(marca),
                    font_size=TAM_EIXO,
                    fill=COR_TEXTO,
                    text_anchor="middle",
                )
            )
    x_agora = px(rel.agora)
    s.append(
        texto(
            x_agora + AFASTAMENTO_ROTULO,
            y1 + DY_HORA,
            "agora",
            font_size=TAM_EIXO,
            fill=COR_TEXTO_2,
        )
    )
    s.append(
        texto(
            x_agora + AFASTAMENTO_ROTULO,
            y1 + DY_DATA,
            agora_txt,
            font_size=TAM_EIXO,
            fill=COR_TEXTO,
        )
    )

    # Linha ideal: do escopo planejado no início da primeira sprint a 0 no fim da última
    s.append(
        f'<line x1="{px(inicio):.1f}" y1="{py(rel.planejado):.1f}" x2="{px(ultima.fim):.1f}" '
        f'y2="{py(0):.1f}" stroke="{COR_IDEAL}" stroke-width="{LARGURA_LINHA}" '
        f'stroke-dasharray="{TRACO_IDEAL}"/>'
    )

    if rel.serie:
        visiveis = rel.serie[inicio_visivel(rel.serie) :]
        primeiro = visiveis[0]
        escopo = [(px(p.momento), py(p.escopo)) for p in visiveis]
        restante = [(px(p.momento), py(p.restante)) for p in visiveis]
        for pontos_px, cor, largura in (
            (escopo, COR_ESCOPO, LARGURA_LINHA),
            (restante, COR_REAL, LARGURA_LINHA_REAL),
        ):
            s.append(
                f'<path d="{caminho_degraus(pontos_px, x_agora)}" fill="none" stroke="{cor}" '
                f'stroke-width="{largura}" stroke-linejoin="round" stroke-linecap="round"/>'
            )

        # Marco do cadastro do backlog, quando ele veio depois do início
        if primeiro.momento > inicio:
            cadastro = fmt_intervalo(rel.serie[0].momento, primeiro.momento)
            rotulo = f"backlog cadastrado ({cadastro})"
            xc, yc = px(primeiro.momento), py(primeiro.restante)
            s.append(
                f'<circle cx="{xc:.1f}" cy="{yc:.1f}" r="{RAIO_PONTO}" fill="{COR_REAL}" '
                f'stroke="{COR_FUNDO}" stroke-width="{ANEL_PONTO}"/>'
            )
            if len(rotulo) * LARGURA_CARACTERE < xc - x0:
                s.append(anotacao(xc - AFASTAMENTO_ROTULO, yc - AFASTAMENTO_ROTULO, rotulo, "end"))
            else:
                s.append(anotacao(xc + AFASTAMENTO_ROTULO, yc - AFASTAMENTO_ROTULO, rotulo))

        # Inclusões de escopo depois do planejamento
        for grupo in agrupar_adicoes(rel.adicionados):
            depois = max(
                (p for p in rel.serie if p.momento <= grupo[-1].criada), key=lambda p: p.momento
            )
            pts = sum(i.peso for i in grupo)
            quando = fmt_intervalo(grupo[0].criada, grupo[-1].criada)
            s.append(
                anotacao(
                    px(grupo[0].criada) - AFASTAMENTO_ROTULO,
                    py(depois.escopo) - AFASTAMENTO_ROTULO,
                    f"+{fmt_pts(pts)} pts: {refs(grupo)} ({quando})",
                    "end",
                )
            )

        # Valores finais, à direita
        final = rel.serie[-1]
        rotulos = [
            (py(final.restante), f"{fmt_pts(final.restante)} restantes", COR_REAL, COR_TEXTO),
            (py(final.escopo), f"{fmt_pts(final.escopo)} no escopo", COR_ESCOPO, COR_TEXTO_2),
        ]
        ys = afastar_rotulos([r[0] for r in rotulos], SEPARACAO_MIN_ROTULOS)
        for (y_ponto, rotulo, cor, cor_texto), y_rotulo in zip(rotulos, ys, strict=True):
            s.append(
                f'<circle cx="{x_agora:.1f}" cy="{y_ponto:.1f}" r="{RAIO_PONTO}" fill="{cor}" '
                f'stroke="{COR_FUNDO}" stroke-width="{ANEL_PONTO}"/>'
            )
            s.append(
                texto(
                    x_agora + AFASTAMENTO_ROTULO,
                    y_rotulo + TAM_TEXTO * CENTRO_TEXTO,
                    rotulo,
                    font_size=TAM_TEXTO,
                    fill=cor_texto,
                )
            )

    y = y1 + DY_NOTAS
    for linha in linhas_nota:
        s.append(texto(MARGEM_LATERAL_TEXTO, y, linha, font_size=TAM_TEXTO, fill=COR_TEXTO_2))
        y += ALTURA_LINHA_NOTA
    s.append("</svg>")
    return "\n".join(s) + "\n"


# ---------------------------------------------------------------- Markdown e terminal


def celula(valor: str) -> str:
    return valor.replace("|", "\\|")


def renderizar_md(rel: Relatorio) -> str:
    gerado = local(rel.agora).strftime("%d/%m/%Y %H:%M")
    com_sem_conclusao = any(r.sem_conclusao for r in rel.por_sprint)
    cab = [
        "Sprint",
        "Período",
        "Planejado",
        "Adicionado depois",
        "Concluído na sprint",
        "Concluído após o fim",
        "Em aberto",
    ]
    if com_sem_conclusao:
        cab.append("Fechado sem conclusão")
    md = [
        "# Burndown",
        "",
        f"Gerado em {gerado} (horário de Brasília) a partir do GitHub Project "
        f"[Radar Público](https://github.com/users/{DONO}/projects/{NUMERO_PROJETO}). "
        f"Para atualizar, rode `{COMANDO}` na raiz do repositório.",
        "",
        f"![Burndown das sprints]({NOME_SVG})",
        "",
        "## Pontos por sprint",
        "",
        "| " + " | ".join(cab) + " |",
        "|---|---|" + "--:|" * (len(cab) - 2),
    ]

    def linha(titulo: str, periodo: str, valores: Sequence[float], negrito: bool = False) -> str:
        celulas = [fmt_pts(v) for v in valores[:-1]]
        if com_sem_conclusao:
            celulas.append(fmt_pts(valores[-1]))
        if negrito:
            titulo, celulas = f"**{titulo}**", [f"**{c}**" for c in celulas]
        return f"| {titulo} | {periodo} | " + " | ".join(celulas) + " |"

    colunas = [
        [r.planejado, r.adicionado, r.no_prazo, r.depois, r.em_aberto, r.sem_conclusao]
        for r in rel.por_sprint
    ]
    for r, valores in zip(rel.por_sprint, colunas, strict=True):
        md.append(linha(r.titulo, periodo_sprint(r.sprint) if r.sprint else "—", valores))
    if len(colunas) > 1:
        md.append(linha("Total", "", [sum(c) for c in zip(*colunas, strict=True)], negrito=True))
    md += [
        "",
        "Planejado: issues criadas até o fim da primeira sprint. Concluído na sprint: fechada "
        "antes do fim dela; após o fim: fechada depois. Em pontos (campo Pontos).",
        "",
        "## Pontos por responsável",
        "",
        "| Responsável | Atribuídos | Concluídos | Concluídos dentro da sprint |",
        "|---|--:|--:|--:|",
    ]
    for r in rel.por_responsavel:
        nome = r.login if r.login == SEM_RESPONSAVEL else f"@{r.login}"
        md.append(
            f"| {nome} | {fmt_pts(r.atribuido)} | {fmt_pts(r.concluido)} | {fmt_pts(r.no_prazo)} |"
        )
    md += ["", "## Notas", ""]
    md += [f"- {n}" for n in notas(rel)]
    if rel.avisos:
        md += ["", "## Avisos sobre os dados", ""]
        md += [f"- {a}" for a in rel.avisos]
    md += [
        "",
        "<details>",
        f"<summary>Issues do Project ({len(rel.itens)})</summary>",
        "",
        "| Issue | Título | Sprint | Pontos | Responsável | Criada | Fechada | Situação |",
        "|---|---|---|--:|---|---|---|---|",
    ]
    titulos = {s.id: s.titulo for s in rel.sprints}
    for i in rel.itens:
        md.append(
            "| "
            + " | ".join(
                [
                    f"#{i.numero}",
                    celula(i.titulo),
                    titulos.get(i.sprint_id, "—"),
                    fmt_pts(i.pontos) if i.pontos is not None else "—",
                    ", ".join(f"@{r}" for r in i.responsaveis) or "—",
                    fmt_momento(i.criada),
                    fmt_momento(i.fechada) if i.fechada else "—",
                    situacao(i, rel),
                ]
            )
            + " |"
        )
    md += ["", "</details>", ""]
    return "\n".join(md)


def resumo_terminal(rel: Relatorio, caminhos: Sequence[Path]) -> str:
    adicionado = sum(i.peso for i in rel.adicionados)
    linhas = [
        "Burndown gravado em " + " e ".join(str(c) for c in caminhos),
        f"Escopo: {fmt_pts(rel.escopo)} pts ({fmt_pts(rel.planejado)} planejados + "
        f"{fmt_pts(adicionado)} adicionados). Concluídos: {fmt_pts(rel.concluido)}. "
        f"Restantes: {fmt_pts(rel.restante)}.",
    ]
    for r in rel.por_sprint:
        extra = f" + {fmt_pts(r.adicionado)} adicionados" if r.adicionado else ""
        linhas.append(
            f"{r.titulo}: {fmt_pts(r.planejado)} planejados{extra}; "
            f"{fmt_pts(r.no_prazo)} concluídos na sprint, {fmt_pts(r.depois)} após o fim, "
            f"{fmt_pts(r.em_aberto)} em aberto."
        )
    linhas.append("Notas:")
    linhas += [f"- {n}" for n in notas(rel)]
    if rel.avisos:
        linhas.append("Avisos sobre os dados:")
        linhas += [f"- {a}" for a in rel.avisos]
    else:
        linhas.append("Nenhum aviso sobre os dados.")
    return "\n".join(linhas)


# ---------------------------------------------------------------- busca e linha de comando


def executar_gh(argumentos: Sequence[str]) -> str:
    gh = shutil.which("gh")
    if gh is None:
        raise ErroDados("o GitHub CLI (gh) não foi encontrado no PATH")
    # Só o gh, achado no PATH, com argumentos montados aqui e sem shell.
    resultado = subprocess.run(  # nosec B603
        [gh, *argumentos], capture_output=True, text=True, check=False
    )
    if resultado.returncode != 0:
        raise ErroDados(f"gh falhou: {resultado.stderr.strip()}")
    return resultado.stdout


def buscar_projeto(
    executar: Callable[[Sequence[str]], str] = executar_gh,
    dono: str = DONO,
    numero: int = NUMERO_PROJETO,
) -> dict:
    """Busca as iterações e todos os itens do Project, página por página."""
    variaveis = {
        "dono": dono,
        "campoPontos": CAMPO_PONTOS,
        "campoSprint": CAMPO_SPRINT,
        "campoStatus": CAMPO_STATUS,
    }
    inteiros = {
        "numero": numero,
        "porPagina": ITENS_POR_PAGINA,
        "maxResponsaveis": MAX_RESPONSAVEIS,
        "maxPrs": MAX_PRS_POR_ISSUE,
    }
    cursor, itens, configuracao = None, [], None
    while True:
        args = ["api", "graphql", "-f", f"query={CONSULTA}"]
        args += [a for k, v in variaveis.items() for a in ("-f", f"{k}={v}")]
        args += [a for k, v in inteiros.items() for a in ("-F", f"{k}={v}")]
        if cursor:
            args += ["-f", f"depois={cursor}"]
        resposta = json.loads(executar(args))
        if resposta.get("errors"):
            raise ErroDados(f"erro na consulta: {resposta['errors']}")
        projeto = ((resposta.get("data") or {}).get("user") or {}).get("projectV2")
        if projeto is None:
            raise ErroDados(f"Project {numero} de {dono} não encontrado")
        if configuracao is None:
            campo = projeto.get("sprint") or {}
            if "configuration" not in campo:
                raise ErroDados(f"o Project não tem o campo de iteração {CAMPO_SPRINT}")
            configuracao = campo["configuration"]
        pagina = projeto["items"]
        itens += pagina["nodes"]
        if not pagina["pageInfo"]["hasNextPage"]:
            return {"sprints": configuracao, "itens": itens}
        cursor = pagina["pageInfo"]["endCursor"]


def ler_agora(valor: str | None) -> datetime:
    if valor is None:
        return datetime.now(UTC)
    momento = datetime.fromisoformat(valor)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=FUSO)
    return momento.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", type=Path, help="dump JSON salvo antes (não usa a rede)")
    parser.add_argument("--salvar-dump", type=Path, help="grava os dados buscados neste JSON")
    parser.add_argument("--agora", help="momento final do gráfico, ISO 8601 (padrão: agora)")
    parser.add_argument("--saida", type=Path, default=DIR_SAIDA, help="pasta dos arquivos")
    args = parser.parse_args(argv)

    try:
        if args.entrada:
            bruto = json.loads(args.entrada.read_text(encoding="utf-8"))
        else:
            bruto = buscar_projeto()
        if args.salvar_dump:
            texto_dump = json.dumps(bruto, ensure_ascii=False, indent=1)
            args.salvar_dump.write_text(texto_dump + "\n", encoding="utf-8")
        sprints = ler_sprints(bruto["sprints"])
        itens, avisos = ler_itens(bruto["itens"])
        rel = calcular(itens, sprints, ler_agora(args.agora), avisos)
    except (ErroDados, KeyError, ValueError, OSError) as erro:
        print(f"burndown: {erro}", file=sys.stderr)
        return 1

    args.saida.mkdir(parents=True, exist_ok=True)
    svg, md = args.saida / NOME_SVG, args.saida / NOME_MD
    svg.write_text(renderizar_svg(rel), encoding="utf-8")
    md.write_text(renderizar_md(rel), encoding="utf-8")
    exibidos = [c.relative_to(RAIZ) if c.is_relative_to(RAIZ) else c for c in (svg, md)]
    print(resumo_terminal(rel, exibidos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
