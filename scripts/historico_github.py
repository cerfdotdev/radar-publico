"""Gera o histórico do GitHub por integrante para o relatório final.

Junta três fontes e grava `docs/relatorio/historico.md`. Também atualiza os blocos gerados de
`docs/relatorio.md`, entre os marcadores `<!-- historico:nome -->` e `<!-- /historico:nome -->`;
o texto fora dos marcadores não muda.

- o GitHub Project "Radar Público" (Pontos, Sprint e responsáveis), com a consulta do burndown;
- as issues e os PRs do repositório: autor, revisões, commits de cada PR e como cada issue fechou;
- o `git log` da main (`origin/main` por padrão): autor, data de autoria e assunto dos commits.

Uso, a partir da raiz do repositório (só biblioteca padrão; precisa do `gh` com escopo `project`):

    git fetch origin                                            # atualiza a origin/main local
    python3 scripts/historico_github.py                         # busca tudo e grava em docs/
    python3 scripts/historico_github.py --salvar-dump dados.json
    python3 scripts/historico_github.py --entrada dados.json    # usa um dump salvo, sem rede
    python3 scripts/historico_github.py --agora 2026-10-20T15:00:00-03:00

Regras usadas:

- Commits são os do histórico da main, contados pela data de autoria em horário de Brasília.
  Commits de merge (mais de um pai) contam à parte: merge de PR ou merge entre branches.
- O login do autor vem do GitHub (autor de cada commit nos PRs). O e-mail só liga os commits fora
  de PRs a esse login e nunca vai para o Markdown. Contas de bot contam como automação.
- O PR de um commit é o PR que ele mergeou ou o primeiro PR mergeado que o contém.
- Revisões contam para quem revisou, em qualquer estado, menos as do autor no próprio PR.
- Issue fechada conta para quem está atribuído nela (como no burndown), não para quem fechou.
- Responsável planejado vem de `scripts/responsaveis.json`; issue fora dele usa a atribuição.
- Eventos depois de `--agora` ficam de fora; o estado de issues e PRs é o do momento da busca.

Testes e lint (dentro de `scripts/`, com as ferramentas de `.github/ci/requirements.txt`):

    python -m pytest
    ruff check historico_github.py tests && ruff format --check historico_github.py tests
"""

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import burndown as bd

# Origem dos dados
DONO = bd.DONO
REPOSITORIO = "radar-publico"
URL_REPO = f"https://github.com/{DONO}/{REPOSITORIO}"
REF_PADRAO = "origin/main"
ITENS_POR_PAGINA = 50
MAX_COMMITS_POR_PR = 100
MAX_REVISOES_POR_PR = 100
MAX_ISSUES_POR_PR = 20
MAX_RESPONSAVEIS = bd.MAX_RESPONSAVEIS
MAX_PRS_POR_ISSUE = bd.MAX_PRS_POR_ISSUE

# Equipe e categorias de quem não é da equipe
LIDER = "cerfdotdev"


@dataclass(frozen=True)
class Integrante:
    login: str
    nome: str
    papel: str


EQUIPE = (
    Integrante(LIDER, "Carlos Rodrigues", "Líder técnico"),
    Integrante("joaoarenda", "João Arenda", "Backend"),
    Integrante("Alisson-dutra", "Alisson Dutra", "Frontend e desktop"),
)
LOGINS_EQUIPE = frozenset(m.login for m in EQUIPE)
AUTOMACAO = "automação"
OUTROS = "outros"
SEM_CONTA = "(sem conta)"
ORIGEM_NAO_IDENTIFICADA = "não identificada"
SUFIXO_BOT = "[bot]"
TIPO_BOT = "Bot"
NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com$")
MERGE_DE_PR = re.compile(r"^Merge pull request #(?P<numero>\d+)")

# Estados e textos do GitHub
ESTADO_ABERTO = "OPEN"
PREFIXO_DAILY = "Daily"
TIPO_PR = "PullRequest"
TIPO_COMMIT = "Commit"

# Arquivos
RAIZ = bd.RAIZ
DIR_SAIDA = bd.DIR_SAIDA
NOME_HISTORICO = Path("relatorio") / "historico.md"
NOME_RELATORIO = "relatorio.md"
ARQ_RESPONSAVEIS = Path(__file__).resolve().parent / "responsaveis.json"
COMANDO = "python3 scripts/historico_github.py"
MARCADOR_INICIO = "<!-- historico:{nome} -->"
MARCADOR_FIM = "<!-- /historico:{nome} -->"
RAIZ_DOCS_HISTORICO = "../"  # de docs/relatorio/ para docs/
ANCORA_LIDER = "commits-do-líder-em-prs-de-colegas"

# git log: um registro por commit, campos separados por caracteres de controle
SEPARADOR_CAMPO = "\x1f"
SEPARADOR_REGISTRO = "\x1e"
FORMATO_LOG = "%H%x1f%P%x1f%aI%x1f%an%x1f%ae%x1f%s%x1e"
CAMPOS_LOG = ("oid", "pais", "autoria", "nome", "email", "assunto")
TAM_OID_CURTO = 7

# Tipos de evento, na ordem das colunas
COMMIT = "commits"
MERGE = "merges"
PR_ABERTO = "prs_abertos"
PR_MERGEADO = "prs_mergeados"
MERGEOU = "mergeou"
REVISAO = "revisoes"
ISSUE_FECHADA = "issues_fechadas"
COLUNAS = (
    (COMMIT, "Commits"),
    (MERGE, "Merges"),
    (PR_ABERTO, "PRs abertos"),
    (PR_MERGEADO, "PRs mergeados"),
    (MERGEOU, "PRs que mergeou"),
    (REVISAO, "Revisões"),
    (ISSUE_FECHADA, "Issues fechadas"),
)
TIPO_MERGE_PR = "merge do PR"
TIPO_MERGE_BRANCH = "merge entre branches"
DIRETO_NA_MAIN = "direto na main"
AUTOR_DO_PR = "autor"
LIDER_NO_PR = "lider"
CHAVES_LIDER = (
    (AUTOR_DO_PR, False),
    (AUTOR_DO_PR, True),
    (LIDER_NO_PR, False),
    (LIDER_NO_PR, True),
)

CONSULTA_PRS = """
query($dono: String!, $repo: String!, $depois: String, $porPagina: Int!,
      $maxCommits: Int!, $maxRevisoes: Int!, $maxIssues: Int!) {
  repository(owner: $dono, name: $repo) {
    pullRequests(first: $porPagina, after: $depois, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state createdAt mergedAt closedAt baseRefName
        author { __typename login }
        mergedBy { __typename login }
        mergeCommit { oid }
        closingIssuesReferences(first: $maxIssues) { nodes { number } }
        reviews(first: $maxRevisoes) {
          totalCount
          nodes { author { __typename login } state submittedAt }
        }
        commits(first: $maxCommits) {
          totalCount
          nodes { commit { oid parents { totalCount } author { name user { login } } } }
        }
      }
    }
  }
}
"""

CONSULTA_ISSUES = """
query($dono: String!, $repo: String!, $depois: String, $porPagina: Int!,
      $maxResponsaveis: Int!, $maxPrs: Int!) {
  repository(owner: $dono, name: $repo) {
    issues(first: $porPagina, after: $depois, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state stateReason createdAt closedAt
        assignees(first: $maxResponsaveis) { nodes { login } }
        comments { totalCount }
        timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {
          nodes {
            ... on ClosedEvent {
              createdAt
              actor { __typename login }
              closer { __typename ... on PullRequest { number } ... on Commit { oid } }
            }
          }
        }
        closedByPullRequestsReferences(first: $maxPrs, includeClosedPrs: true) {
          nodes { number }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Commit:
    oid: str
    pais: tuple[str, ...]
    momento: datetime
    nome: str
    email: str
    assunto: str

    @property
    def merge(self) -> bool:
        return len(self.pais) > 1

    @property
    def curto(self) -> str:
        return self.oid[:TAM_OID_CURTO]


@dataclass(frozen=True)
class CommitPr:
    oid: str
    login: str | None
    nome: str
    merge: bool


@dataclass(frozen=True)
class Revisao:
    autor: str
    estado: str
    momento: datetime


@dataclass(frozen=True)
class PullRequest:
    numero: int
    titulo: str
    autor: str
    estado: str
    criado: datetime
    mergeado: datetime | None
    fechado: datetime | None
    base: str
    mergeado_por: str | None
    merge_oid: str | None
    fecha: tuple[int, ...]
    revisoes: tuple[Revisao, ...]
    commits: tuple[CommitPr, ...]


@dataclass(frozen=True)
class Issue:
    numero: int
    titulo: str
    estado: str
    motivo: str | None
    criada: datetime
    fechada: datetime | None
    responsaveis: tuple[str, ...]
    comentarios: int
    fechada_por: str | None
    fechada_pelo_pr: int | None
    fechada_pelo_commit: str | None
    prs: tuple[int, ...]


@dataclass(frozen=True)
class Evento:
    login: str
    momento: datetime
    tipo: str
    ref: str
    pontos: float = 0.0


@dataclass(frozen=True)
class Historico:
    agora: datetime
    ref: str
    oid_ref: str
    commits: tuple[Commit, ...]
    autores: Mapping[str, str]
    pr_do_commit: Mapping[str, int | None]
    prs: Mapping[int, PullRequest]
    issues: Mapping[int, Issue]
    planejado: Mapping[int, tuple[str, ...]]
    rel: bd.Relatorio
    eventos: tuple[Evento, ...]
    dias: tuple[date, ...]
    contas: tuple[tuple[str, str, str, int], ...]
    avisos: tuple[str, ...]

    def item(self, numero: int) -> bd.Item | None:
        return next((i for i in self.rel.itens if i.numero == numero), None)


# ---------------------------------------------------------------- leitura dos dados


def login_ator(ator: dict | None) -> str:
    """Login de um autor do GitHub; bots ganham o sufixo [bot], como no git."""
    if not ator:
        return SEM_CONTA
    login = ator["login"]
    if ator.get("__typename") == TIPO_BOT and not login.endswith(SUFIXO_BOT):
        login += SUFIXO_BOT
    return login


def eh_bot(login: str) -> bool:
    return login.endswith(SUFIXO_BOT)


def categoria(login: str) -> str:
    """Integrante da equipe pelo login; o resto vira automação ou outros."""
    if login in LOGINS_EQUIPE or login == bd.SEM_RESPONSAVEL:
        return login
    return AUTOMACAO if eh_bot(login) else OUTROS


def ler_git_log(texto: str) -> list[dict]:
    """Registros do `git log --format=FORMATO_LOG`, como dicionários (o formato do dump)."""
    registros = []
    for bruto in texto.split(SEPARADOR_REGISTRO):
        bruto = bruto.strip("\n")
        if not bruto:
            continue
        campos = dict(zip(CAMPOS_LOG, bruto.split(SEPARADOR_CAMPO), strict=True))
        campos["pais"] = campos["pais"].split()
        registros.append(campos)
    return registros


def ler_commits(registros: Iterable[dict]) -> list[Commit]:
    commits = [
        Commit(
            oid=r["oid"],
            pais=tuple(r["pais"]),
            momento=bd.ler_momento(r["autoria"]),
            nome=r["nome"],
            email=r["email"],
            assunto=r["assunto"],
        )
        for r in registros
    ]
    return sorted(commits, key=lambda c: c.momento)


def ler_prs(nos: Iterable[dict]) -> tuple[list[PullRequest], list[str]]:
    prs, avisos = [], []
    for no in nos:
        numero = no["number"]
        for conexao in ("commits", "reviews"):
            if no[conexao]["totalCount"] > len(no[conexao]["nodes"]):
                avisos.append(f"PR #{numero}: só parte de {conexao} foi lida")
        commits = tuple(
            CommitPr(
                oid=c["commit"]["oid"],
                login=(c["commit"]["author"].get("user") or {}).get("login"),
                nome=c["commit"]["author"]["name"],
                merge=c["commit"]["parents"]["totalCount"] > 1,
            )
            for c in no["commits"]["nodes"]
        )
        revisoes = tuple(
            Revisao(login_ator(r["author"]), r["state"], bd.ler_momento(r["submittedAt"]))
            for r in no["reviews"]["nodes"]
            if r["submittedAt"]
        )
        prs.append(
            PullRequest(
                numero=numero,
                titulo=no["title"],
                autor=login_ator(no["author"]),
                estado=no["state"],
                criado=bd.ler_momento(no["createdAt"]),
                mergeado=bd.ler_momento(no["mergedAt"]),
                fechado=bd.ler_momento(no["closedAt"]),
                base=no["baseRefName"],
                mergeado_por=login_ator(no["mergedBy"]) if no["mergedBy"] else None,
                merge_oid=(no["mergeCommit"] or {}).get("oid") if no["mergedAt"] else None,
                fecha=tuple(sorted(i["number"] for i in no["closingIssuesReferences"]["nodes"])),
                revisoes=tuple(sorted(revisoes, key=lambda r: r.momento)),
                commits=commits,
            )
        )
    return sorted(prs, key=lambda p: p.numero), avisos


def ler_issues(nos: Iterable[dict]) -> list[Issue]:
    issues = []
    for no in nos:
        aberta = no["state"] == ESTADO_ABERTO
        eventos = no["timelineItems"]["nodes"]
        fechamento = eventos[-1] if eventos and not aberta else {}
        closer = fechamento.get("closer") or {}
        issues.append(
            Issue(
                numero=no["number"],
                titulo=no["title"],
                estado=no["state"],
                motivo=no["stateReason"],
                criada=bd.ler_momento(no["createdAt"]),
                fechada=None if aberta else bd.ler_momento(no["closedAt"]),
                responsaveis=tuple(a["login"] for a in no["assignees"]["nodes"]),
                comentarios=no["comments"]["totalCount"],
                fechada_por=login_ator(fechamento["actor"]) if fechamento.get("actor") else None,
                fechada_pelo_pr=closer.get("number")
                if closer.get("__typename") == TIPO_PR
                else None,
                fechada_pelo_commit=closer.get("oid")
                if closer.get("__typename") == TIPO_COMMIT
                else None,
                prs=tuple(
                    sorted(p["number"] for p in no["closedByPullRequestsReferences"]["nodes"])
                ),
            )
        )
    return sorted(issues, key=lambda i: i.numero)


def ler_planejado(registros: Iterable[dict]) -> dict[int, tuple[str, ...]]:
    """Responsável planejado de cada issue (`scripts/responsaveis.json`)."""
    planejado: dict[int, list[str]] = defaultdict(list)
    for r in registros:
        planejado[r["issue"]].append(r["login"])
    return {numero: tuple(logins) for numero, logins in planejado.items()}


# ---------------------------------------------------------------- cálculo


def login_noreply(email: str) -> str | None:
    achado = NOREPLY.match(email)
    return achado["login"] if achado else None


def resolver_autores(
    commits: Sequence[Commit], prs: Iterable[PullRequest]
) -> tuple[dict[str, str], tuple[tuple[str, str, str, int], ...], list[str]]:
    """Login de cada commit, as contas por nome no git e avisos.

    O login vem do autor do commit nos PRs (o GitHub liga o e-mail à conta); commits fora de PRs
    usam o login aprendido para o mesmo e-mail, ou o e-mail noreply do GitHub.
    """
    por_oid = {c.oid: c.login for pr in prs for c in pr.commits if c.login}
    aprendidos: dict[str, set[str]] = defaultdict(set)
    for commit in commits:
        if commit.oid in por_oid:
            aprendidos[commit.email].add(por_oid[commit.oid])
    avisos = []
    por_email: dict[str, str] = {}
    origem: dict[str, str] = {}
    for commit in commits:
        email = commit.email
        if email in por_email:
            continue
        if login := login_noreply(email):
            por_email[email], origem[email] = login, "e-mail noreply do GitHub"
        elif aprendidos[email]:
            logins = sorted(aprendidos[email])
            if len(logins) > 1:
                avisos.append(f"o autor {commit.nome} aparece com as contas {bd.juntar(logins)}")
            por_email[email], origem[email] = logins[0], "autor dos commits nos PRs"
        else:
            por_email[email], origem[email] = OUTROS, ORIGEM_NAO_IDENTIFICADA
            avisos.append(f"autor sem conta do GitHub identificada: {commit.nome}")
    autores = {c.oid: por_oid.get(c.oid) or por_email[c.email] for c in commits}
    contagem = Counter((c.nome, c.email) for c in commits)
    contas = tuple(
        sorted(
            ((nome, por_email[email], origem[email], n) for (nome, email), n in contagem.items()),
            key=lambda conta: (-conta[3], conta[0]),
        )
    )
    return autores, contas, avisos


def pr_de_cada_commit(
    commits: Iterable[Commit], prs: Iterable[PullRequest]
) -> dict[str, int | None]:
    """PR pelo qual cada commit entrou: o que ele mergeou, ou o primeiro mergeado que o contém."""
    prs = list(prs)
    por_merge = {pr.merge_oid: pr.numero for pr in prs if pr.merge_oid}
    contem: dict[str, list[PullRequest]] = defaultdict(list)
    for pr in prs:
        for c in pr.commits:
            contem[c.oid].append(pr)

    def ordem(pr: PullRequest) -> tuple:
        return (pr.mergeado is None, pr.mergeado or pr.criado, pr.numero)

    resultado: dict[str, int | None] = {}
    for commit in commits:
        if commit.oid in por_merge:
            resultado[commit.oid] = por_merge[commit.oid]
        elif contem[commit.oid]:
            resultado[commit.oid] = min(contem[commit.oid], key=ordem).numero
        elif commit.merge and (achado := MERGE_DE_PR.match(commit.assunto)):
            resultado[commit.oid] = int(achado["numero"])
        else:
            resultado[commit.oid] = None
    return resultado


def tipo_merge(commit: Commit, prs: Mapping[int, PullRequest]) -> str:
    if any(pr.merge_oid == commit.oid for pr in prs.values()):
        return TIPO_MERGE_PR
    if MERGE_DE_PR.match(commit.assunto):
        return TIPO_MERGE_PR
    return TIPO_MERGE_BRANCH


def responsaveis_da_issue(issue: Issue, item: bd.Item | None) -> tuple[str, ...]:
    """Atribuição atual: a do Project (a mesma do burndown) ou, fora dele, a da issue."""
    return item.responsaveis if item else issue.responsaveis


def gerar_eventos(
    commits: Iterable[Commit],
    autores: Mapping[str, str],
    prs: Iterable[PullRequest],
    issues: Iterable[Issue],
    itens: Mapping[int, bd.Item],
    agora: datetime,
) -> list[Evento]:
    eventos = []
    for c in commits:
        eventos.append(
            Evento(categoria(autores[c.oid]), c.momento, MERGE if c.merge else COMMIT, c.curto)
        )
    for pr in prs:
        ref = f"#{pr.numero}"
        eventos.append(Evento(categoria(pr.autor), pr.criado, PR_ABERTO, ref))
        if pr.mergeado:
            eventos.append(Evento(categoria(pr.autor), pr.mergeado, PR_MERGEADO, ref))
            if pr.mergeado_por:
                eventos.append(Evento(categoria(pr.mergeado_por), pr.mergeado, MERGEOU, ref))
        for r in pr.revisoes:
            if r.autor != pr.autor:
                eventos.append(Evento(categoria(r.autor), r.momento, REVISAO, ref))
    for issue in issues:
        if not issue.fechada:
            continue
        item = itens.get(issue.numero)
        logins = responsaveis_da_issue(issue, item) or (bd.SEM_RESPONSAVEL,)
        concluida = item.concluida if item else issue.motivo not in bd.MOTIVOS_SEM_CONCLUSAO
        parte = (item.peso if item and concluida else 0.0) / len(logins)
        for login in logins:
            eventos.append(
                Evento(categoria(login), issue.fechada, ISSUE_FECHADA, f"#{issue.numero}", parte)
            )
    return sorted((e for e in eventos if e.momento <= agora), key=lambda e: e.momento)


def dia_local(momento: datetime) -> date:
    return bd.local(momento).date()


def dias_do_periodo(eventos: Sequence[Evento]) -> list[date]:
    """Todos os dias do primeiro ao último evento, inclusive os sem atividade."""
    if not eventos:
        return []
    primeiro, ultimo = dia_local(eventos[0].momento), dia_local(eventos[-1].momento)
    return [primeiro + timedelta(days=n) for n in range((ultimo - primeiro).days + 1)]


def contar(eventos: Iterable[Evento], login: str, dia: date | None = None) -> Counter[str]:
    return Counter(
        e.tipo for e in eventos if e.login == login and (dia is None or dia_local(e.momento) == dia)
    )


def pontos_fechados(eventos: Iterable[Evento], login: str, dia: date | None = None) -> float:
    return sum(
        e.pontos
        for e in eventos
        if e.login == login
        and e.tipo == ISSUE_FECHADA
        and (dia is None or dia_local(e.momento) == dia)
    )


def janela(eventos: Iterable[Evento], login: str, dia: date) -> tuple[datetime, datetime] | None:
    momentos = [e.momento for e in eventos if e.login == login and dia_local(e.momento) == dia]
    return (min(momentos), max(momentos)) if momentos else None


def categorias(eventos: Iterable[Evento]) -> list[str]:
    """A equipe sempre, depois as outras categorias que tiveram eventos."""
    presentes = {e.login for e in eventos}
    extras = [c for c in (AUTOMACAO, OUTROS, bd.SEM_RESPONSAVEL) if c in presentes]
    return [m.login for m in EQUIPE] + extras


def montar(bruto: Mapping, planejado: Mapping[int, tuple[str, ...]], agora: datetime) -> Historico:
    projeto = bruto["projeto"]
    sprints = bd.ler_sprints(projeto["sprints"])
    itens, avisos_projeto = bd.ler_itens(projeto["itens"])
    rel = bd.calcular(itens, sprints, agora, avisos_projeto)
    prs_lidos, avisos = ler_prs(bruto["repositorio"]["prs"])
    issues = ler_issues(bruto["repositorio"]["issues"])
    todos = ler_commits(bruto["git"]["commits"])
    commits = [c for c in todos if c.momento <= agora]
    autores, contas, avisos_autores = resolver_autores(commits, prs_lidos)
    avisos += avisos_autores
    por_numero = {i.numero: i for i in rel.itens}
    for issue in issues:
        if issue.numero not in por_numero:
            avisos.append(f"#{issue.numero} não está no Project (sem Pontos e Sprint)")
    numeros = {i.numero for i in issues}
    for numero in sorted(set(planejado) - numeros):
        avisos.append(f"#{numero} está em responsaveis.json, mas não existe no repositório")
    eventos = gerar_eventos(commits, autores, prs_lidos, issues, por_numero, agora)
    return Historico(
        agora=agora,
        ref=bruto["git"]["ref"],
        oid_ref=bruto["git"]["oid"],
        commits=tuple(commits),
        autores=autores,
        pr_do_commit=pr_de_cada_commit(commits, prs_lidos),
        prs={pr.numero: pr for pr in prs_lidos},
        issues={i.numero: i for i in issues},
        planejado=dict(planejado),
        rel=rel,
        eventos=tuple(eventos),
        dias=tuple(dias_do_periodo(eventos)),
        contas=contas,
        avisos=tuple(avisos) + rel.avisos,
    )


def planejados_da_issue(hist: Historico, numero: int) -> tuple[str, ...]:
    issue, item = hist.issues[numero], hist.item(numero)
    return hist.planejado.get(numero) or responsaveis_da_issue(issue, item) or (bd.SEM_RESPONSAVEL,)


def divergencias(hist: Historico) -> list[tuple[Issue, tuple[str, ...], tuple[str, ...]]]:
    """Issues cuja atribuição atual difere do responsável planejado."""
    saida = []
    for numero, issue in hist.issues.items():
        if numero not in hist.planejado:
            continue
        atribuidos = responsaveis_da_issue(issue, hist.item(numero))
        if set(atribuidos) != set(hist.planejado[numero]):
            saida.append((issue, hist.planejado[numero], atribuidos))
    return saida


def commits_em_prs_de_colegas(hist: Historico) -> dict[int, list[Commit]]:
    """Commits da main que entraram por PRs de outro integrante, sem o merge do próprio PR."""
    por_pr: dict[int, list[Commit]] = defaultdict(list)
    for commit in hist.commits:
        numero = hist.pr_do_commit.get(commit.oid)
        pr = hist.prs.get(numero) if numero else None
        if pr and pr.autor in LOGINS_EQUIPE - {LIDER} and commit.oid != pr.merge_oid:
            por_pr[pr.numero].append(commit)
    return dict(sorted(por_pr.items()))


def commits_do_lider_em_prs_de_colegas(hist: Historico) -> list[tuple[PullRequest, Commit]]:
    """Commits do líder (correções e merges de atualização) nas branches de PRs de colegas."""
    return [
        (hist.prs[numero], c)
        for numero, commits in commits_em_prs_de_colegas(hist).items()
        for c in commits
        if hist.autores[c.oid] == LIDER
    ]


# ---------------------------------------------------------------- textos


def fmt_data(dia: date) -> str:
    return dia.strftime("%d/%m")


def nome_conta(login: str) -> str:
    if login in (AUTOMACAO, OUTROS, bd.SEM_RESPONSAVEL, SEM_CONTA):
        return login
    return f"{login} (automação)" if eh_bot(login) else f"@{login}"


def link_issue(numero: int) -> str:
    return f"[#{numero}]({URL_REPO}/issues/{numero})"


def link_pr(numero: int) -> str:
    return f"[#{numero}]({URL_REPO}/pull/{numero})"


def link_commit(oid: str) -> str:
    return f"[`{oid[:TAM_OID_CURTO]}`]({URL_REPO}/commit/{oid})"


def titulo(nivel: int, texto: str) -> str:
    return f"{'#' * nivel} {texto}"


def linha(celulas: Iterable[str]) -> str:
    return "| " + " | ".join(celulas) + " |"


def cabecalho(nomes: Sequence[str], numericas: int = 0) -> list[str]:
    """Cabeçalho de tabela; as últimas `numericas` colunas ficam alinhadas à direita."""
    alinhamentos = ["---"] * (len(nomes) - numericas) + ["--:"] * numericas
    return [linha(nomes), "|" + "|".join(alinhamentos) + "|"]


def negrito(celulas: Iterable[str]) -> list[str]:
    return [f"**{c}**" if c else c for c in celulas]


def sprint_do_dia(dia: date, sprints: Sequence[bd.Sprint]) -> str:
    for s in sprints:
        if dia_local(s.inicio) <= dia < dia_local(s.fim):
            return s.titulo
    if sprints and dia < dia_local(sprints[0].inicio):
        return "antes das sprints"
    return "após as sprints"


def estado_pr(pr: PullRequest) -> str:
    if pr.mergeado:
        return bd.fmt_momento(pr.mergeado)
    if pr.estado == ESTADO_ABERTO:
        return "aberto"
    return f"fechado sem merge ({bd.fmt_momento(pr.fechado)})" if pr.fechado else "fechado"


def prs_da_issue(hist: Historico, issue: Issue) -> str:
    numeros = set(issue.prs) | {p.numero for p in hist.prs.values() if issue.numero in p.fecha}
    partes = []
    for numero in sorted(numeros):
        pr = hist.prs.get(numero)
        if pr is None or pr.mergeado:
            partes.append(link_pr(numero))
        elif pr.estado == ESTADO_ABERTO:
            partes.append(f"{link_pr(numero)} (aberto)")
        else:
            partes.append(f"{link_pr(numero)} (fechado sem merge)")
    return ", ".join(partes) or "—"


def como_fechou(issue: Issue) -> str:
    if not issue.fechada:
        return "—"
    if issue.fechada_pelo_pr:
        return f"pelo PR {link_pr(issue.fechada_pelo_pr)}"
    if issue.fechada_pelo_commit:
        return f"pelo commit {link_commit(issue.fechada_pelo_commit)}"
    quem = f" por {nome_conta(issue.fechada_por)}" if issue.fechada_por else ""
    return f"manual{quem}"


def situacao_issue(hist: Historico, issue: Issue) -> str:
    item = hist.item(issue.numero)
    if item:
        return bd.situacao(item, hist.rel)
    return "em aberto" if not issue.fechada else "fechada"


def resumo_commits_pr(hist: Historico, pr: PullRequest) -> str:
    """Commits do PR por autor: 'N' ou 'N + M merges'."""
    contagem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for c in pr.commits:
        login = hist.autores.get(c.oid) or c.login or c.nome
        contagem[login][1 if c.merge else 0] += 1
    partes = []
    for login, (normais, merges) in contagem.items():
        textos = [str(normais)] if normais else []
        if merges:
            textos.append(f"{merges} merge" + ("s" if merges > 1 else ""))
        partes.append(f"{nome_conta(login)} {' + '.join(textos)}")
    return "; ".join(partes) or "—"


def resumo_revisoes(pr: PullRequest) -> str:
    partes = []
    for r in pr.revisoes:
        extra = " (do autor)" if r.autor == pr.autor else ""
        partes.append(f"{nome_conta(r.autor)} {r.estado} {bd.fmt_momento(r.momento)}{extra}")
    return "; ".join(partes) or "—"


def fmt_horario(intervalo: tuple[datetime, datetime] | None) -> str:
    if intervalo is None:
        return "—"
    inicio, fim = (bd.fmt_hora(m) for m in intervalo)
    return inicio if inicio == fim else f"{inicio}–{fim}"


def fmt_pontos(valor: float) -> str:
    return f"{bd.fmt_pts(valor)} {'pt' if valor == 1 else 'pts'}"


def fmt_issues_fechadas(quantidade: int, pontos: float) -> str:
    if not quantidade:
        return "0"
    return f"{quantidade} ({fmt_pontos(pontos)})"


def rodape(hist: Historico) -> str:
    gerado = bd.local(hist.agora).strftime("%d/%m/%Y %H:%M")
    return (
        f"Gerado em {gerado} (horário de Brasília) a partir do `git log` de `{hist.ref}` "
        f"(commit {link_commit(hist.oid_ref)}), das issues e PRs de [{DONO}/{REPOSITORIO}]"
        f"({URL_REPO}) e do [Project](https://github.com/users/{DONO}/projects/"
        f"{bd.NUMERO_PROJETO}). Para atualizar, rode `git fetch origin`, `{bd.COMANDO}` e "
        f"`{COMANDO}` na raiz do repositório."
    )


# ---------------------------------------------------------------- blocos de Markdown


def bloco_resumo(hist: Historico) -> list[str]:
    nomes = ["Integrante", "Papel"] + [n for _, n in COLUNAS] + ["Pontos concluídos"]
    md = cabecalho(nomes, len(COLUNAS) + 1)
    papeis = {m.login: m.papel for m in EQUIPE}
    totais: Counter[str] = Counter()
    pts_total = 0.0
    for login in categorias(hist.eventos):
        cont = contar(hist.eventos, login)
        pts = pontos_fechados(hist.eventos, login)
        totais += cont
        pts_total += pts
        valores = [str(cont[t]) for t, _ in COLUNAS]
        md.append(linha([nome_conta(login), papeis.get(login, "—"), *valores, bd.fmt_pts(pts)]))
    valores = [str(totais[t]) for t, _ in COLUNAS] + [bd.fmt_pts(pts_total)]
    md.append(linha(negrito(["Total", "", *valores])))
    md += [
        "",
        "Commits: na main, sem os merges, que ficam na coluna Merges. PRs mergeados: os do "
        "integrante; PRs que mergeou: quem apertou o merge. Revisões: enviadas em PRs de outra "
        "pessoa, em qualquer estado. Issues fechadas: atribuídas ao integrante, com os pontos "
        "do Project.",
    ]
    return md


def bloco_commits_por_dia(hist: Historico) -> list[str]:
    sprints = hist.rel.sprints
    nomes = ["Integrante"]
    nomes += [f"{fmt_data(d)} ({sprint_do_dia(d, sprints)})" for d in hist.dias]
    nomes.append("Total")
    md = cabecalho(nomes, len(hist.dias) + 1)
    for login in categorias(hist.eventos):
        por_dia = [contar(hist.eventos, login, d)[COMMIT] for d in hist.dias]
        md.append(linha([nome_conta(login), *map(str, por_dia), str(sum(por_dia))]))
    return md


def bloco_diario(hist: Historico, nivel: int) -> list[str]:
    """Tabela por dia de cada integrante, com o horário da primeira e da última atividade."""
    md: list[str] = []
    nomes = ["Dia", "Sprint", "Horário"] + [n for _, n in COLUNAS]
    for membro in EQUIPE:
        md += ["", titulo(nivel, f"@{membro.login}: {membro.nome} ({membro.papel})"), ""]
        md += cabecalho(nomes, len(COLUNAS))
        for dia in hist.dias:
            cont = contar(hist.eventos, membro.login, dia)
            intervalo = janela(hist.eventos, membro.login, dia)
            horario = fmt_horario(intervalo)
            valores = [str(cont[t]) for t, _ in COLUNAS[:-1]]
            pts = pontos_fechados(hist.eventos, membro.login, dia)
            valores.append(fmt_issues_fechadas(cont[ISSUE_FECHADA], pts))
            md.append(
                linha([fmt_data(dia), sprint_do_dia(dia, hist.rel.sprints), horario, *valores])
            )
        cont = contar(hist.eventos, membro.login)
        valores = [str(cont[t]) for t, _ in COLUNAS[:-1]]
        pts = pontos_fechados(hist.eventos, membro.login)
        valores.append(fmt_issues_fechadas(cont[ISSUE_FECHADA], pts))
        md.append(linha(negrito(["Total", "", "", *valores])))
    return md[1:]


def bloco_pontos(hist: Historico, raiz: str = "") -> list[str]:
    plano: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for numero in hist.issues:
        item = hist.item(numero)
        logins = planejados_da_issue(hist, numero)
        for login in logins:
            plano[login][0] += 1
            plano[login][1] += (item.peso if item else 0.0) / len(logins)
    por_login = {r.login: r for r in hist.rel.por_responsavel}
    nomes = [
        "Integrante",
        "Issues pelo plano",
        "Pontos pelo plano",
        "Pontos atribuídos",
        "Pontos concluídos",
        "Concluídos dentro da sprint",
    ]
    md = cabecalho(nomes, len(nomes) - 1)
    logins = [m.login for m in EQUIPE] + sorted((set(plano) | set(por_login)) - LOGINS_EQUIPE)
    for login in logins:
        r = por_login.get(login)
        md.append(
            linha(
                [
                    nome_conta(login),
                    str(plano[login][0]),
                    bd.fmt_pts(plano[login][1]),
                    bd.fmt_pts(r.atribuido if r else 0),
                    bd.fmt_pts(r.concluido if r else 0),
                    bd.fmt_pts(r.no_prazo if r else 0),
                ]
            )
        )
    fora = sorted(n for n in hist.issues if n not in hist.planejado)
    md += [
        "",
        "Pelo plano: responsável de cada issue em `scripts/responsaveis.json`"
        + (
            f"; as issues fora do arquivo ({bd.juntar([f'#{n}' for n in fora])}) contam para "
            "quem está atribuído"
            if fora
            else ""
        )
        + ". Atribuídos, concluídos e dentro da sprint seguem a atribuição atual no Project e "
        f"são os mesmos números de [`burndown.md`]({raiz}burndown.md) quando os dois são "
        "gerados juntos.",
    ]
    if divergencias(hist):
        md.append("")
    for issue, plano_issue, atribuidos in divergencias(hist):
        item = hist.item(issue.numero)
        pts = f", {fmt_pontos(item.peso)}" if item else ""
        md.append(
            f"- {link_issue(issue.numero)} ({bd.celula(issue.titulo)}{pts}): planejada para "
            f"{bd.juntar([nome_conta(x) for x in plano_issue])}, atribuída a "
            f"{bd.juntar([nome_conta(x) for x in atribuidos]) or 'ninguém'} no Project."
        )
    return md


def bloco_tarefas(hist: Historico, nivel: int) -> list[str]:
    titulos = {s.id: s.titulo for s in hist.rel.sprints}
    nomes = ["Issue", "Título", "Pontos", "Sprint", "Fechada", "Como fechou", "PRs", "Situação"]
    md: list[str] = []
    for membro in EQUIPE:
        numeros = [n for n in hist.issues if membro.login in planejados_da_issue(hist, n)]
        md += ["", titulo(nivel, f"@{membro.login}: {membro.nome} ({membro.papel})"), ""]
        if not numeros:
            md.append("Nenhuma issue.")
            continue
        md += cabecalho(nomes)
        for numero in numeros:
            issue, item = hist.issues[numero], hist.item(numero)
            atribuidos = responsaveis_da_issue(issue, item)
            situacao = situacao_issue(hist, issue)
            if membro.login not in atribuidos:
                quem = bd.juntar([nome_conta(x) for x in atribuidos]) or "ninguém"
                situacao += f"; atribuída a {quem}"
            md.append(
                linha(
                    [
                        link_issue(numero),
                        bd.celula(issue.titulo),
                        bd.fmt_pts(item.pontos) if item and item.pontos is not None else "—",
                        titulos.get(item.sprint_id, "—") if item else "—",
                        bd.fmt_momento(issue.fechada) if issue.fechada else "em aberto",
                        como_fechou(issue),
                        prs_da_issue(hist, issue),
                        situacao,
                    ]
                )
            )
    return md[1:]


def bloco_lider(hist: Historico) -> list[str]:
    """Por PR de colega: commits do autor, do líder e de outros que entraram na main por ele."""
    nomes = [
        "PR",
        "Autor do PR",
        "Commits do autor",
        "Merges do autor",
        "Commits do líder",
        "Merges do líder",
        "De outros",
    ]
    md = cabecalho(nomes, len(nomes) - 2)
    totais: Counter[tuple[str, bool]] = Counter()
    for numero, commits in commits_em_prs_de_colegas(hist).items():
        pr = hist.prs[numero]
        cont: Counter[tuple[str, bool]] = Counter()
        for c in commits:
            login = hist.autores[c.oid]
            quem = AUTOR_DO_PR if login == pr.autor else LIDER_NO_PR if login == LIDER else OUTROS
            cont[(quem, c.merge)] += 1
        totais += cont
        valores = [cont[k] for k in CHAVES_LIDER]
        valores.append(cont[(OUTROS, False)] + cont[(OUTROS, True)])
        md.append(linha([link_pr(numero), nome_conta(pr.autor), *map(str, valores)]))
    valores = [totais[k] for k in CHAVES_LIDER]
    valores.append(totais[(OUTROS, False)] + totais[(OUTROS, True)])
    md.append(linha(negrito(["Total", "", *map(str, valores)])))
    md += [
        "",
        f"Commits do líder (@{LIDER}) que entraram na main por PRs abertos por colegas: "
        "correções feitas na revisão, na própria branch do PR. Merges: atualizações da branch "
        "com a main ou com outra branch; o merge do próprio PR não entra.",
    ]
    return md


def bloco_dailies(hist: Historico) -> list[str]:
    dailies = [i for i in hist.issues.values() if i.titulo.startswith(PREFIXO_DAILY)]
    md = []
    for issue in dailies:
        estado = "aberta" if not issue.fechada else f"fechada em {bd.fmt_momento(issue.fechada)}"
        md.append(
            f"- {link_issue(issue.numero)} {bd.celula(issue.titulo)}: {issue.comentarios} "
            f"comentário{'s' if issue.comentarios != 1 else ''} ({estado})."
        )
    total = sum(i.comentarios for i in hist.issues.values())
    md.append(
        f"- Nas {len(hist.issues)} issues do repositório há {total} "
        f"comentário{'s' if total != 1 else ''} no total."
    )
    return md


def bloco_abertas(hist: Historico) -> list[str]:
    """Issues ainda abertas, com pontos, responsável atual e PRs ligados."""
    md = []
    for issue in hist.issues.values():
        if issue.fechada:
            continue
        item = hist.item(issue.numero)
        partes = [fmt_pontos(item.peso)] if item else []
        quem = bd.juntar([nome_conta(x) for x in responsaveis_da_issue(issue, item)])
        partes.append(quem or "sem responsável")
        prs = prs_da_issue(hist, issue)
        if prs != "—":
            partes.append(f"PR {prs}")
        md.append(f"- {link_issue(issue.numero)} {bd.celula(issue.titulo)}: {', '.join(partes)}.")
    return md or ["- Nenhuma issue aberta."]


def bloco_burndown(hist: Historico) -> list[str]:
    rel = hist.rel
    nomes = [
        "Sprint",
        "Período",
        "Planejado",
        "Adicionado depois",
        "Concluído na sprint",
        "Concluído após o fim",
        "Em aberto",
    ]
    md = cabecalho(nomes, len(nomes) - 2)
    colunas = [
        [r.planejado, r.adicionado, r.no_prazo, r.depois, r.em_aberto] for r in rel.por_sprint
    ]
    for r, valores in zip(rel.por_sprint, colunas, strict=True):
        periodo = bd.periodo_sprint(r.sprint) if r.sprint else "—"
        md.append(linha([r.titulo, periodo, *map(bd.fmt_pts, valores)]))
    if len(colunas) > 1:
        totais = [bd.fmt_pts(sum(c)) for c in zip(*colunas, strict=True)]
        md.append(linha(negrito(["Total", "", *totais])))
    md += [
        "",
        f"Escopo atual: {bd.fmt_pts(rel.escopo)} pts. Concluídos: {bd.fmt_pts(rel.concluido)}. "
        f"Restantes: {bd.fmt_pts(rel.restante)}. Em pontos (campo Pontos do Project).",
        "",
    ]
    md += [f"- {n}" for n in bd.notas(rel)]
    return md


def bloco_gerado(hist: Historico) -> list[str]:
    return [rodape(hist)]


def blocos_relatorio(hist: Historico) -> dict[str, str]:
    """Conteúdo de cada bloco gerado de `docs/relatorio.md`."""
    blocos = {
        "gerado": bloco_gerado(hist),
        "pontos": bloco_pontos(hist),
        "tarefas": bloco_tarefas(hist, 4),
        "resumo": bloco_resumo(hist),
        "commits-por-dia": bloco_commits_por_dia(hist),
        "diario": bloco_diario(hist, 4),
        "lider": bloco_lider(hist)
        + [
            "",
            "A lista de cada um desses commits está em "
            f"[`relatorio/historico.md`]({NOME_HISTORICO.as_posix()}#{ANCORA_LIDER}).",
        ],
        "dailies": bloco_dailies(hist),
        "abertas": bloco_abertas(hist),
        "burndown": bloco_burndown(hist),
    }
    return {nome: "\n".join(md) for nome, md in blocos.items()}


def atualizar_blocos(texto: str, blocos: Mapping[str, str]) -> tuple[str, list[str]]:
    """Troca o conteúdo entre os marcadores de cada bloco; devolve os marcadores ausentes."""
    ausentes = []
    for nome, conteudo in blocos.items():
        inicio, fim = MARCADOR_INICIO.format(nome=nome), MARCADOR_FIM.format(nome=nome)
        a = texto.find(inicio)
        b = texto.find(fim, a + len(inicio)) if a >= 0 else -1
        if b < 0:
            ausentes.append(nome)
            continue
        texto = f"{texto[: a + len(inicio)]}\n\n{conteudo.strip()}\n\n{texto[b:]}"
    return texto, ausentes


# ---------------------------------------------------------------- historico.md


def secao_prs(hist: Historico) -> list[str]:
    nomes = [
        "PR",
        "Título",
        "Autor",
        "Base",
        "Aberto",
        "Mergeado",
        "Mergeado por",
        "Commits por autor",
        "Revisões",
        "Fecha",
    ]
    md = cabecalho(nomes)
    for pr in hist.prs.values():
        md.append(
            linha(
                [
                    link_pr(pr.numero),
                    bd.celula(pr.titulo),
                    nome_conta(pr.autor),
                    f"`{pr.base}`",
                    bd.fmt_momento(pr.criado),
                    estado_pr(pr),
                    nome_conta(pr.mergeado_por) if pr.mergeado_por else "—",
                    resumo_commits_pr(hist, pr),
                    resumo_revisoes(pr),
                    ", ".join(link_issue(n) for n in pr.fecha) or "—",
                ]
            )
        )
    md += [
        "",
        "Commits por autor: todos os commits do PR, como o GitHub os lista (os de PR aberto "
        "ainda não estão na main). Revisões marcadas (do autor) são respostas do próprio autor "
        "e não contam como revisão feita.",
    ]
    return md


def secao_commits_lider(hist: Historico) -> list[str]:
    lista = commits_do_lider_em_prs_de_colegas(hist)
    md = cabecalho(["PR", "Autor do PR", "Dia", "Hora", "Commit", "Tipo", "Assunto"])
    for pr, c in lista:
        md.append(
            linha(
                [
                    link_pr(pr.numero),
                    nome_conta(pr.autor),
                    bd.fmt_dia(c.momento),
                    bd.fmt_hora(c.momento),
                    link_commit(c.oid),
                    TIPO_MERGE_BRANCH if c.merge else "commit",
                    bd.celula(c.assunto),
                ]
            )
        )
    return md


def ref_pr_do_commit(hist: Historico, commit: Commit) -> str:
    numero = hist.pr_do_commit.get(commit.oid)
    return link_pr(numero) if numero else DIRETO_NA_MAIN


def secao_commits(hist: Historico, nivel: int) -> list[str]:
    md: list[str] = []
    normais = [c for c in hist.commits if not c.merge]
    for dia in hist.dias:
        do_dia = [c for c in normais if dia_local(c.momento) == dia]
        md += ["", titulo(nivel, f"{fmt_data(dia)} ({sprint_do_dia(dia, hist.rel.sprints)})"), ""]
        if not do_dia:
            md.append("Nenhum commit.")
            continue
        md += cabecalho(["Hora", "Autor", "Commit", "Assunto", "PR"])
        for c in do_dia:
            md.append(
                linha(
                    [
                        bd.fmt_hora(c.momento),
                        nome_conta(hist.autores[c.oid]),
                        link_commit(c.oid),
                        bd.celula(c.assunto),
                        ref_pr_do_commit(hist, c),
                    ]
                )
            )
    return md[1:]


def secao_merges(hist: Historico) -> list[str]:
    md = cabecalho(["Dia", "Hora", "Autor", "Commit", "Tipo", "PR", "Assunto"])
    for c in (c for c in hist.commits if c.merge):
        md.append(
            linha(
                [
                    bd.fmt_dia(c.momento),
                    bd.fmt_hora(c.momento),
                    nome_conta(hist.autores[c.oid]),
                    link_commit(c.oid),
                    tipo_merge(c, hist.prs),
                    ref_pr_do_commit(hist, c),
                    bd.celula(c.assunto),
                ]
            )
        )
    return md


def secao_contas(hist: Historico) -> list[str]:
    md = cabecalho(["Nome do autor no git", "Conta", "Como foi ligada", "Commits na main"], 1)
    for nome, login, origem, n in hist.contas:
        md.append(linha([bd.celula(nome), nome_conta(login), origem, str(n)]))
    md += [
        "",
        "Cada linha é um par nome e e-mail de autor no git; os e-mails não são listados aqui.",
    ]
    return md


def renderizar_historico(hist: Historico) -> str:
    md = [
        "# Histórico do GitHub por integrante",
        "",
        rodape(hist),
        "",
        "Gerado por `scripts/historico_github.py`; não edite à mão. O relatório que usa estas "
        "tabelas é [`docs/relatorio.md`](../relatorio.md).",
        "",
        "## Regras",
        "",
        "- Commits: os do histórico da main, pela data de autoria, em horário de Brasília "
        f"({bd.NOME_FUSO}). Commits de merge contam à parte.",
        "- Conta de cada autor: a que o GitHub liga aos commits dos PRs. Bots contam como "
        "automação.",
        "- PR de um commit: o PR que ele mergeou ou o primeiro PR mergeado que o contém; sem PR, "
        f"{DIRETO_NA_MAIN}.",
        "- Revisões: enviadas em PRs de outra pessoa, em qualquer estado. DISMISSED é uma "
        "aprovação descartada depois de um commit novo no PR.",
        "- Issues fechadas: contam para quem está atribuído na issue, não para quem fechou.",
        "",
        "## Resumo por integrante",
        "",
        *bloco_resumo(hist),
        "",
        "## Commits por dia",
        "",
        *bloco_commits_por_dia(hist),
        "",
        "## Atividade diária por integrante",
        "",
        *bloco_diario(hist, 3),
        "",
        "## Pontos por integrante",
        "",
        *bloco_pontos(hist, RAIZ_DOCS_HISTORICO),
        "",
        "## Tarefas por integrante",
        "",
        *bloco_tarefas(hist, 3),
        "",
        "## Pull requests",
        "",
        *secao_prs(hist),
        "",
        "## Commits do líder em PRs de colegas",
        "",
        *bloco_lider(hist),
        "",
        *secao_commits_lider(hist),
        "",
        "## Commits na main, sem merges",
        "",
        *secao_commits(hist, 3),
        "",
        "## Commits de merge",
        "",
        *secao_merges(hist),
        "",
        "## Dailies",
        "",
        *bloco_dailies(hist),
        "",
        "## Contas dos autores",
        "",
        *secao_contas(hist),
    ]
    if hist.avisos:
        md += ["", "## Avisos sobre os dados", ""]
        md += [f"- {a}" for a in hist.avisos]
    return "\n".join(md) + "\n"


def resumo_terminal(hist: Historico, gravados: Sequence[str], ausentes: Sequence[str]) -> str:
    linhas = [f"Histórico gravado em {bd.juntar(list(gravados))}"]
    for login in categorias(hist.eventos):
        cont = contar(hist.eventos, login)
        partes = [f"{cont[t]} {n.lower()}" for t, n in COLUNAS]
        pts = bd.fmt_pts(pontos_fechados(hist.eventos, login))
        linhas.append(f"{nome_conta(login)}: {', '.join(partes)}; {pts} pts concluídos.")
    lider = commits_do_lider_em_prs_de_colegas(hist)
    normais = sum(1 for _, c in lider if not c.merge)
    linhas.append(
        f"Commits do líder em PRs de colegas: {normais} commits e {len(lider) - normais} merges."
    )
    diretos = sum(1 for c in hist.commits if hist.pr_do_commit.get(c.oid) is None)
    linhas.append(f"Commits na main sem PR: {diretos}.")
    for issue, plano, atribuidos in divergencias(hist):
        linhas.append(
            f"#{issue.numero}: planejada para {bd.juntar(list(plano))}, "
            f"atribuída a {bd.juntar(list(atribuidos)) or 'ninguém'}."
        )
    if ausentes:
        linhas.append(f"Marcadores ausentes em {NOME_RELATORIO}: {bd.juntar(list(ausentes))}.")
    if hist.avisos:
        linhas.append("Avisos sobre os dados:")
        linhas += [f"- {a}" for a in hist.avisos]
    else:
        linhas.append("Nenhum aviso sobre os dados.")
    return "\n".join(linhas)


# ---------------------------------------------------------------- busca e linha de comando


def executar_git(argumentos: Sequence[str]) -> str:
    git = shutil.which("git")
    if git is None:
        raise bd.ErroDados("o git não foi encontrado no PATH")
    # Só o git, achado no PATH, com argumentos montados aqui e sem shell.
    resultado = subprocess.run(  # nosec B603
        [git, "-C", str(RAIZ), *argumentos], capture_output=True, text=True, check=False
    )
    if resultado.returncode != 0:
        raise bd.ErroDados(f"git falhou: {resultado.stderr.strip()}")
    return resultado.stdout


def buscar_git(ref: str, executar: Callable[[Sequence[str]], str] = executar_git) -> dict:
    oid = executar(["rev-parse", "--verify", f"{ref}^{{commit}}"]).strip()
    texto = executar(["log", f"--format={FORMATO_LOG}", oid])
    return {"ref": ref, "oid": oid, "commits": ler_git_log(texto)}


def buscar_conexao(
    consulta: str,
    campo: str,
    inteiros: Mapping[str, int],
    executar: Callable[[Sequence[str]], str],
) -> list[dict]:
    """Todos os nós de uma conexão do repositório (`pullRequests` ou `issues`), por página."""
    cursor, nos = None, []
    while True:
        args = ["api", "graphql", "-f", f"query={consulta}"]
        args += ["-f", f"dono={DONO}", "-f", f"repo={REPOSITORIO}"]
        args += [a for k, v in inteiros.items() for a in ("-F", f"{k}={v}")]
        if cursor:
            args += ["-f", f"depois={cursor}"]
        resposta = json.loads(executar(args))
        if resposta.get("errors"):
            raise bd.ErroDados(f"erro na consulta: {resposta['errors']}")
        repositorio = (resposta.get("data") or {}).get("repository")
        if repositorio is None:
            raise bd.ErroDados(f"repositório {DONO}/{REPOSITORIO} não encontrado")
        pagina = repositorio[campo]
        nos += pagina["nodes"]
        if not pagina["pageInfo"]["hasNextPage"]:
            return nos
        cursor = pagina["pageInfo"]["endCursor"]


def buscar_repositorio(executar: Callable[[Sequence[str]], str] = bd.executar_gh) -> dict:
    prs = buscar_conexao(
        CONSULTA_PRS,
        "pullRequests",
        {
            "porPagina": ITENS_POR_PAGINA,
            "maxCommits": MAX_COMMITS_POR_PR,
            "maxRevisoes": MAX_REVISOES_POR_PR,
            "maxIssues": MAX_ISSUES_POR_PR,
        },
        executar,
    )
    issues = buscar_conexao(
        CONSULTA_ISSUES,
        "issues",
        {
            "porPagina": ITENS_POR_PAGINA,
            "maxResponsaveis": MAX_RESPONSAVEIS,
            "maxPrs": MAX_PRS_POR_ISSUE,
        },
        executar,
    )
    return {"prs": prs, "issues": issues}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", type=Path, help="dump JSON salvo antes (sem rede e sem git)")
    parser.add_argument("--salvar-dump", type=Path, help="grava os dados buscados neste JSON")
    parser.add_argument("--agora", help="ignora eventos depois deste momento, ISO 8601")
    parser.add_argument("--ref", default=REF_PADRAO, help=f"ref do git (padrão: {REF_PADRAO})")
    parser.add_argument("--saida", type=Path, default=DIR_SAIDA, help="pasta docs/ de saída")
    parser.add_argument(
        "--responsaveis", type=Path, default=ARQ_RESPONSAVEIS, help="responsáveis planejados"
    )
    args = parser.parse_args(argv)

    try:
        if args.entrada:
            bruto = json.loads(args.entrada.read_text(encoding="utf-8"))
        else:
            bruto = {
                "projeto": bd.buscar_projeto(),
                "repositorio": buscar_repositorio(),
                "git": buscar_git(args.ref),
            }
        if args.salvar_dump:
            texto_dump = json.dumps(bruto, ensure_ascii=False, indent=1)
            args.salvar_dump.write_text(texto_dump + "\n", encoding="utf-8")
        planejado = ler_planejado(json.loads(args.responsaveis.read_text(encoding="utf-8")))
        hist = montar(bruto, planejado, bd.ler_agora(args.agora))
    except (bd.ErroDados, KeyError, ValueError, OSError) as erro:
        print(f"historico: {erro}", file=sys.stderr)
        return 1

    destino = args.saida / NOME_HISTORICO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(renderizar_historico(hist), encoding="utf-8")
    gravados = [destino]
    relatorio = args.saida / NOME_RELATORIO
    ausentes: list[str] = []
    if relatorio.exists():
        texto, ausentes = atualizar_blocos(
            relatorio.read_text(encoding="utf-8"), blocos_relatorio(hist)
        )
        relatorio.write_text(texto, encoding="utf-8")
        gravados.append(relatorio)
    exibidos = [str(c.relative_to(RAIZ) if c.is_relative_to(RAIZ) else c) for c in gravados]
    print(resumo_terminal(hist, exibidos, ausentes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
