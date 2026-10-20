"""Cliente HTTP da API do Radar Público, sem depender do Qt.

O app desktop usa as mesmas buscas do frontend web (docs/api.md): nome exato ou
similar, limite, cargo, órgão, UF e paginação.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, fields
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .config import api_url_from_env

DEFAULT_TIMEOUT_S = 20.0
LIMITE_MIN = 1
LIMITE_MAX = 100
LIMITE_PADRAO = 100
POR_PAGINA_PADRAO = 20
POR_PAGINA_OPCOES = (20, 50, 100)


class ApiError(Exception):
    """Falha de rede, HTTP ou formato que pode ser mostrada ao usuário."""

    def __init__(
        self,
        mensagem: str,
        *,
        status: int | None = None,
        codigo: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.codigo = codigo
        self.retry_after = retry_after

    @property
    def message(self) -> str:
        return self.mensagem

    @property
    def code(self) -> str | None:
        return self.codigo


@dataclass(frozen=True)
class Busca:
    """Filtros de uma busca; campos vazios não entram na query."""

    nome: str = ""
    similar: str = ""
    limite: int = LIMITE_PADRAO
    cargo: str = ""
    orgao: str = ""
    uf: str = ""
    pagina: int = 1
    por_pagina: int = POR_PAGINA_PADRAO

    def parametros(self) -> list[tuple[str, str]]:
        if self.nome and self.similar:
            raise ValueError("Use nome exato ou similar, não os dois.")
        parametros: list[tuple[str, str]] = []
        if self.nome:
            parametros.append(("nome", self.nome))
        if self.similar:
            parametros.append(("similar", self.similar))
            parametros.append(("limit", str(self.limite)))
        if self.cargo:
            parametros.append(("cargo", self.cargo))
        if self.orgao:
            parametros.append(("orgao", self.orgao))
        if self.uf:
            parametros.append(("uf", self.uf))
        # A busca por similaridade não é paginada: usa apenas o limite.
        if not self.similar:
            if self.pagina != 1:
                parametros.append(("page", str(self.pagina)))
            if self.por_pagina != POR_PAGINA_PADRAO:
                parametros.append(("per_page", str(self.por_pagina)))
        return parametros

    # Aliases em inglês para facilitar integrações e testes.
    @property
    def limit(self) -> int:
        return self.limite

    @property
    def page(self) -> int:
        return self.pagina

    @property
    def per_page(self) -> int:
        return self.por_pagina


SearchQuery = Busca

_ALIASES = {
    "limit": "limite",
    "page": "pagina",
    "per_page": "por_pagina",
}
_CAMPOS = {campo.name for campo in fields(Busca)}


def montar_parametros(**filtros: Any) -> list[tuple[str, str]]:
    """Valida os nomes dos filtros e devolve a query, útil em testes e integrações."""
    normalizados = {_ALIASES.get(chave, chave): valor for chave, valor in filtros.items()}
    desconhecidos = set(normalizados) - _CAMPOS
    if desconhecidos:
        nomes = ", ".join(sorted(desconhecidos))
        raise TypeError(f"Filtro desconhecido: {nomes}")
    return Busca(**normalizados).parametros()


def _formatar_retry(mensagem: str, retry_after: int | None) -> str:
    if retry_after is None:
        return mensagem
    return f"{mensagem} Tente novamente em {retry_after} s."


def _ler_json(corpo: bytes) -> Any:
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _ler_retry_after(headers: Mapping[str, str] | None) -> int | None:
    if headers is None:
        return None
    valor = headers.get("Retry-After")
    if valor is None:
        return None
    try:
        return max(0, int(valor.strip()))
    except ValueError:
        return None


def _erro_http(status: int, corpo: bytes, headers: Mapping[str, str] | None) -> ApiError:
    dados = _ler_json(corpo)
    erro = dados.get("error") if isinstance(dados, dict) else None
    codigo = erro.get("code") if isinstance(erro, dict) else None
    mensagem = erro.get("message") if isinstance(erro, dict) else None
    retry_after = _ler_retry_after(headers)

    if not isinstance(mensagem, str) or not mensagem:
        mensagem = f"A API respondeu com erro {status}."
    if status in (429, 503):
        mensagem = _formatar_retry(mensagem, retry_after)
    return ApiError(mensagem, status=status, codigo=codigo, retry_after=retry_after)


class RadarApiClient:
    """Cliente de GET /api/servidores e GET /api/servidores/<id>."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        api_url: str | None = None,
    ) -> None:
        self.base_url = (api_url or base_url or api_url_from_env()).strip()
        if not self.base_url:
            raise ValueError("A URL da API não pode ser vazia.")
        self.timeout = timeout

    @property
    def api_url(self) -> str:
        """URL base normalizada, aceitando com ou sem o sufixo /api."""
        base = self.base_url.rstrip("/")
        caminho = urlsplit(base).path.rstrip("/")
        return base if caminho.endswith("/api") else f"{base}/api"

    def _url(self, caminho: str, parametros: list[tuple[str, str]] | None = None) -> str:
        url = f"{self.api_url}/{caminho.lstrip('/')}"
        if parametros:
            url = f"{url}?{urlencode(parametros)}"
        return url

    def _requisitar(self, url: str) -> dict[str, Any]:
        requisicao = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RadarPublicoDesktop/1.0",
            },
        )
        try:
            with urlopen(requisicao, timeout=self.timeout) as resposta:
                corpo = resposta.read()
        except HTTPError as erro:
            try:
                corpo = erro.read()
            finally:
                erro.close()
            raise _erro_http(erro.code, corpo, erro.headers) from erro
        except (TimeoutError, socket.timeout) as erro:
            raise ApiError("A API demorou demais para responder. Tente novamente.") from erro
        except URLError as erro:
            if isinstance(erro.reason, (TimeoutError, socket.timeout)):
                raise ApiError("A API demorou demais para responder. Tente novamente.") from erro
            raise ApiError("Não foi possível conectar à API. Verifique a URL configurada.") from erro
        except OSError as erro:
            raise ApiError("Não foi possível conectar à API. Verifique a URL configurada.") from erro

        dados = _ler_json(corpo)
        if not isinstance(dados, dict):
            raise ApiError("A API respondeu em formato inesperado.")
        return dados

    def buscar(self, busca: Busca | None = None, **filtros: Any) -> dict[str, Any]:
        """Executa GET /api/servidores e devolve o corpo já validado como JSON."""
        if busca is None:
            busca = Busca(**{_ALIASES.get(chave, chave): valor for chave, valor in filtros.items()})
        elif filtros:
            raise TypeError("Passe uma Busca ou filtros, não os dois.")
        dados = self._requisitar(self._url("servidores", busca.parametros()))
        if not isinstance(dados.get("data"), list) or not isinstance(dados.get("meta"), dict):
            raise ApiError("A API respondeu em formato inesperado.")
        return dados

    def detalhar(self, servidor_id: int) -> dict[str, Any]:
        """Executa GET /api/servidores/<id> e devolve o registro do detalhe."""
        dados = self._requisitar(self._url(f"servidores/{int(servidor_id)}"))
        if not isinstance(dados.get("data"), dict):
            raise ApiError("A API respondeu em formato inesperado.")
        return dados["data"]

    # Nomes em inglês mantidos como atalhos para uso externo.
    search = buscar
    detail = detalhar


ApiClient = RadarApiClient
RadarApi = RadarApiClient


def buscar_servidores(
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    api_url: str | None = None,
    **filtros: Any,
) -> dict[str, Any]:
    """Atalho para uma busca única, útil em scripts e testes."""
    return RadarApiClient(base_url, timeout, api_url).buscar(**filtros)
