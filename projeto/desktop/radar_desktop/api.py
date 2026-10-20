"""Cliente HTTP da API do Radar Público (docs/api.md), sem depender do Qt.

Usa só a biblioteca padrão (urllib). Toda falha de rede, HTTP ou formato vira
ApiError com uma mensagem em português pronta para a tela; a interface nunca
recebe uma exceção crua nem um JSON fora do contrato.
"""

import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from http import HTTPStatus
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import validar_url

# Tempo máximo esperando a API, o mesmo do frontend web (SEARCH_TIMEOUT_MS).
TEMPO_LIMITE_S = 20
USER_AGENT = "RadarPublicoDesktop"

LIMITE_MIN = 1
LIMITE_MAX = 100
LIMITE_PADRAO = 100
PAGINA_PADRAO = 1
POR_PAGINA_PADRAO = 20
POR_PAGINA_OPCOES = (20, 50, 100)
# A API para de contar em 10.000 resultados (meta.total_exato = false).
TOTAL_MAXIMO = 10_000


class Situacao(StrEnum):
    ATIVO = "ativo"
    APOSENTADO = "aposentado"
    TODOS = "todos"


@dataclass(frozen=True)
class Busca:
    """Filtros de uma busca; campos vazios e valores padrão não entram na query."""

    nome: str = ""
    similar: str = ""
    limite: int = LIMITE_PADRAO
    cargo: str = ""
    orgao: str = ""
    uf: str = ""
    situacao: Situacao = Situacao.TODOS
    pagina: int = PAGINA_PADRAO
    por_pagina: int = POR_PAGINA_PADRAO

    def parametros(self) -> list[tuple[str, str]]:
        parametros: list[tuple[str, str]] = []
        if self.nome:
            parametros.append(("nome", self.nome))
        if self.similar:
            # 'limit' só é aceito junto com 'similar' (app/search_params.py).
            parametros.append(("similar", self.similar))
            parametros.append(("limit", str(self.limite)))
        for nome, valor in (("cargo", self.cargo), ("orgao", self.orgao), ("uf", self.uf)):
            if valor:
                parametros.append((nome, valor))
        if self.situacao is not Situacao.TODOS:
            parametros.append(("situacao", self.situacao.value))
        # A busca por similaridade não é paginada: devolve até 'limit' resultados.
        if not self.similar:
            if self.pagina != PAGINA_PADRAO:
                parametros.append(("page", str(self.pagina)))
            if self.por_pagina != POR_PAGINA_PADRAO:
                parametros.append(("per_page", str(self.por_pagina)))
        return parametros


@dataclass(frozen=True)
class Servidor:
    """Um vínculo da lista; os campos que a fonte não traz vêm None."""

    id: int
    nome: str
    situacao: Situacao
    cargo: str | None
    orgao: str
    sigla_orgao: str | None
    uf: str | None
    valor: float | None


@dataclass(frozen=True)
class Detalhe(Servidor):
    """GET /api/servidores/<id>: os campos da lista mais os do vínculo."""

    codigo_carreira: str | None
    tipo_aposentadoria: str | None
    fundamento_legal: str | None
    portaria: str | None
    data_aposentadoria: str | None
    forma_ingresso: str | None
    data_ingresso: str | None
    referencia: str | None


CAMPOS_DETALHE = (
    "codigo_carreira",
    "tipo_aposentadoria",
    "fundamento_legal",
    "portaria",
    "data_aposentadoria",
    "forma_ingresso",
    "data_ingresso",
    "referencia",
)


@dataclass(frozen=True)
class Meta:
    total: int
    total_exato: bool
    page: int
    per_page: int
    total_pages: int


@dataclass(frozen=True)
class Resultado:
    """Página de resultados. Sem servidores, é o estado "nenhum vínculo" (meta None)."""

    servidores: tuple[Servidor, ...]
    meta: Meta | None


class ApiError(Exception):
    """Falha que a tela mostra como aviso; `informativo` para limites de uso (429/503)."""

    def __init__(
        self,
        mensagem: str,
        *,
        codigo: str | None = None,
        status: int | None = None,
        retry_after: int | None = None,
        informativo: bool = False,
    ) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.status = status
        self.retry_after = retry_after
        self.informativo = informativo


NAO_ENCONTRADO = "NAO_ENCONTRADO"
TENTE_DE_NOVO = "Tente de novo em instantes."

# Uma mensagem por código de erro do contrato (docs/api.md). {detalhe} recebe a
# mensagem da própria API; {espera} recebe o tempo do header Retry-After.
MENSAGENS_ERRO = {
    "PARAMETRO_DESCONHECIDO": (
        "A API não reconheceu um parâmetro da busca. "
        "Confira se o app e a API estão na mesma versão."
    ),
    "PARAMETRO_INVALIDO": "A API recusou a busca: {detalhe}",
    "FILTRO_OBRIGATORIO": "Informe um nome ou ao menos um filtro: cargo, órgão ou UF.",
    "UF_INVALIDA": "UF inválida. Escolha uma das 27 siglas da lista.",
    "CARGO_NAO_ENCONTRADO": (
        "Nenhum cargo corresponde ao texto informado. Use parte do nome do cargo, como “professor”."
    ),
    "ORGAO_NAO_ENCONTRADO": (
        "Nenhum órgão corresponde ao texto informado. Use parte do nome ou a sigla, como “INSS”."
    ),
    NAO_ENCONTRADO: "Nenhum vínculo encontrado.",
    "PAGINA_INEXISTENTE": (
        "Esta página não existe para a busca atual. Busque de novo a partir da primeira página."
    ),
    "ROTA_INEXISTENTE": (
        "A API não tem este endereço. Confira se a URL configurada termina em /api "
        "e se a API está atualizada."
    ),
    "METODO_NAO_PERMITIDO": "A API recusou o tipo de requisição. Confira a URL configurada.",
    "MUITAS_REQUISICOES": "Muitas buscas em pouco tempo. {espera}",
    "SERVIDOR_OCUPADO": "O serviço está ocupado com muitas buscas ao mesmo tempo. {espera}",
    "TEMPO_ESGOTADO": (
        "A busca demorou demais e foi interrompida. Refine os filtros e tente de novo."
    ),
    "SERVIDOR_INDISPONIVEL": f"A API está fora do ar. {TENTE_DE_NOVO}",
    "ERRO_INTERNO": f"Algo deu errado na API. {TENTE_DE_NOVO}",
}
# Limites de uso: não são erro de quem busca, por isso o tom informativo.
CODIGOS_INFORMATIVOS = ("MUITAS_REQUISICOES", "SERVIDOR_OCUPADO")
# Código do contrato quando o corpo não traz o JSON de erro (ex.: página HTML de um proxy).
CODIGO_POR_STATUS = {
    HTTPStatus.TOO_MANY_REQUESTS: "MUITAS_REQUISICOES",
    HTTPStatus.INTERNAL_SERVER_ERROR: "ERRO_INTERNO",
    HTTPStatus.BAD_GATEWAY: "SERVIDOR_INDISPONIVEL",
    HTTPStatus.SERVICE_UNAVAILABLE: "SERVIDOR_OCUPADO",
    HTTPStatus.GATEWAY_TIMEOUT: "TEMPO_ESGOTADO",
}

MENSAGEM_SEM_CONEXAO = (
    "Não foi possível conectar à API em {url}. Confira se o backend está no ar e a URL configurada."
)
MENSAGEM_TEMPO_LIMITE = f"A API não respondeu em {TEMPO_LIMITE_S} segundos. Tente de novo."
MENSAGEM_NAO_JSON = "A API respondeu, mas não em JSON. Confira a URL configurada."
MENSAGEM_FORMATO = "Resposta inesperada da API: os dados vieram fora do formato combinado."
MENSAGEM_DETALHE_PADRAO = "algum filtro está fora das regras."


def _texto_espera(retry_after: int | None) -> str:
    if retry_after is None:
        return TENTE_DE_NOVO
    unidade = "segundo" if retry_after == 1 else "segundos"
    return f"Tente de novo em {retry_after} {unidade}."


def _ler_retry_after(valor: str | None) -> int | None:
    """Retry-After em segundos; a forma de data HTTP é ignorada."""
    if valor is None:
        return None
    valor = valor.strip()
    return int(valor) if valor.isascii() and valor.isdigit() else None


def _ler_json(corpo: bytes) -> Any:
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _erro_http(status: int, corpo: bytes, retry_after: int | None) -> ApiError:
    dados = _ler_json(corpo)
    erro = dados.get("error") if isinstance(dados, dict) else None
    codigo = erro.get("code") if isinstance(erro, dict) else None
    detalhe = erro.get("message") if isinstance(erro, dict) else None
    if not isinstance(codigo, str):
        codigo = CODIGO_POR_STATUS.get(status)
    if not isinstance(detalhe, str) or not detalhe:
        detalhe = None

    modelo = MENSAGENS_ERRO.get(codigo) if codigo is not None else None
    if modelo is None:
        mensagem = detalhe or f"A API respondeu com erro (HTTP {status})."
    else:
        mensagem = modelo.format(
            detalhe=detalhe or MENSAGEM_DETALHE_PADRAO, espera=_texto_espera(retry_after)
        )
    return ApiError(
        mensagem,
        codigo=codigo,
        status=status,
        retry_after=retry_after,
        informativo=codigo in CODIGOS_INFORMATIVOS,
    )


def _eh_inteiro(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _eh_contagem(valor: Any) -> bool:
    return _eh_inteiro(valor) and valor >= 0


def _eh_texto_ou_nulo(valor: Any) -> bool:
    return valor is None or isinstance(valor, str)


def _eh_valor(valor: Any) -> bool:
    if valor is None:
        return True
    return (_eh_inteiro(valor) or isinstance(valor, float)) and math.isfinite(valor)


def _ler_servidor(item: Any) -> Servidor | None:
    if not isinstance(item, dict):
        return None
    situacoes = (Situacao.ATIVO.value, Situacao.APOSENTADO.value)
    if not (
        _eh_inteiro(item.get("id"))
        and isinstance(item.get("nome"), str)
        and item.get("situacao") in situacoes
        and _eh_texto_ou_nulo(item.get("cargo"))
        and isinstance(item.get("orgao"), str)
        and _eh_texto_ou_nulo(item.get("sigla_orgao"))
        and _eh_texto_ou_nulo(item.get("uf"))
        and _eh_valor(item.get("valor"))
    ):
        return None
    valor = item.get("valor")
    return Servidor(
        id=item["id"],
        nome=item["nome"],
        situacao=Situacao(item["situacao"]),
        cargo=item.get("cargo"),
        orgao=item["orgao"],
        sigla_orgao=item.get("sigla_orgao"),
        uf=item.get("uf"),
        valor=None if valor is None else float(valor),
    )


def _ler_meta(meta: Any) -> Meta | None:
    if not isinstance(meta, dict):
        return None
    contagens = ("total", "page", "per_page", "total_pages")
    if not all(_eh_contagem(meta.get(campo)) for campo in contagens):
        return None
    if not isinstance(meta.get("total_exato"), bool):
        return None
    return Meta(**{campo: meta[campo] for campo in (*contagens, "total_exato")})


def _ler_detalhe(item: Any) -> Detalhe | None:
    servidor = _ler_servidor(item)
    if servidor is None or not all(_eh_texto_ou_nulo(item.get(c)) for c in CAMPOS_DETALHE):
        return None
    return Detalhe(**asdict(servidor), **{campo: item.get(campo) for campo in CAMPOS_DETALHE})


class RadarApiClient:
    """Cliente de GET /api/servidores e GET /api/servidores/<id>."""

    def __init__(self, api_url: str, tempo_limite_s: float = TEMPO_LIMITE_S) -> None:
        self.api_url = validar_url(api_url)
        self.tempo_limite_s = tempo_limite_s

    def _requisitar(self, caminho: str, parametros: list[tuple[str, str]] | None = None) -> Any:
        url = f"{self.api_url}/{caminho}"
        if parametros:
            url = f"{url}?{urlencode(parametros)}"
        requisicao = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            # Esquema limitado a http/https por validar_url.
            with urlopen(requisicao, timeout=self.tempo_limite_s) as resposta:  # nosec B310
                corpo = resposta.read()
        except HTTPError as erro:
            cabecalhos = erro.headers
            retry_after = _ler_retry_after(
                cabecalhos.get("Retry-After") if cabecalhos is not None else None
            )
            try:
                corpo_erro = erro.read()
            except (OSError, HTTPException):
                corpo_erro = b""
            finally:
                erro.close()
            raise _erro_http(erro.code, corpo_erro, retry_after) from erro
        except TimeoutError as erro:
            raise ApiError(MENSAGEM_TEMPO_LIMITE) from erro
        except URLError as erro:
            if isinstance(erro.reason, TimeoutError):
                raise ApiError(MENSAGEM_TEMPO_LIMITE) from erro
            raise ApiError(MENSAGEM_SEM_CONEXAO.format(url=self.api_url)) from erro
        except (OSError, HTTPException) as erro:
            raise ApiError(MENSAGEM_SEM_CONEXAO.format(url=self.api_url)) from erro

        dados = _ler_json(corpo)
        if dados is None:
            raise ApiError(MENSAGEM_NAO_JSON)
        return dados

    def buscar(self, busca: Busca) -> Resultado:
        """GET /api/servidores. 404 NAO_ENCONTRADO vira um resultado vazio, não um erro."""
        try:
            dados = self._requisitar("servidores", busca.parametros())
        except ApiError as erro:
            if erro.codigo == NAO_ENCONTRADO:
                return Resultado(servidores=(), meta=None)
            raise

        itens = dados.get("data") if isinstance(dados, dict) else None
        meta = _ler_meta(dados.get("meta")) if isinstance(dados, dict) else None
        if not isinstance(itens, list) or meta is None:
            raise ApiError(MENSAGEM_FORMATO)
        servidores = tuple(_ler_servidor(item) for item in itens)
        if any(servidor is None for servidor in servidores):
            raise ApiError(MENSAGEM_FORMATO)
        return Resultado(servidores=servidores, meta=meta if servidores else None)

    def detalhar(self, servidor_id: int) -> Detalhe:
        """GET /api/servidores/<id>."""
        dados = self._requisitar(f"servidores/{servidor_id}")
        detalhe = _ler_detalhe(dados.get("data")) if isinstance(dados, dict) else None
        if detalhe is None:
            raise ApiError(MENSAGEM_FORMATO)
        return detalhe
