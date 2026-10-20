"""Cabeçalhos de cache de GET /api/servidores e /api/servidores/<id> (docs/api.md, "Cache").

Os dados só mudam quando a base é recarregada. As respostas 200 e 404 dessas duas rotas saem
com Cache-Control: public, max-age=API_CACHE_TTL_S e um ETag com a versão dos dados, para o
navegador e o nginx do frontend (proxy_cache) reusarem. Todo o resto sai com no-store: 400,
429 e 5xx dependem do cliente ou do momento, e /api/health nunca pode vir de cache. Um
If-None-Match com a versão atual recebe 304 depois da validação e antes de qualquer consulta
da busca. API_CACHE_TTL_S=0 desliga: tudo sai com no-store, sem ETag e sem 304.

A versão é lida uma vez por worker, na primeira busca ou detalhe válido: os meses de
referência com quantas linhas vieram de cada um, e o identificador do cluster do Postgres,
que muda a cada initdb, ou seja, a cada recarga (`docker compose down -v`). Assim o ETag
muda mesmo se uma recarga trouxer os mesmos meses e contagens com outro conteúdo (ex.: uma
correção na normalização da carga).
"""

from http import HTTPStatus

from flask import Flask, Response, current_app, request

from app.db import get_db_connection
from app.lazy import Lazy

EXTENSION_KEY = "http_cache"
CACHEABLE_ENDPOINTS = frozenset({"servidores.listar_servidores", "servidores.detalhar_servidor"})
# O 404 dessas rotas também depende só dos dados (nome, cargo, página ou id inexistente).
# O 304 leva os mesmos cabeçalhos da resposta que ele revalida.
CACHEABLE_STATUSES = frozenset({HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.NOT_MODIFIED})
NO_STORE = "no-store"

# Uma linha por arquivo de origem: o mês de referência e quantos vínculos vieram dele.
LOADS_QUERY = "SELECT referencia, count(*) FROM servidor GROUP BY referencia ORDER BY referencia"
# Criado no initdb; toda recarga começa com o volume do banco vazio.
CLUSTER_QUERY = "SELECT system_identifier FROM pg_control_system()"
LOAD_SEPARATOR = "+"


def load_data_version() -> str:
    """'2026-05:412354+2026-08:1092162@<cluster>' (uma consulta por worker)."""
    with get_db_connection() as conn, conn.cursor() as cur:
        loads = cur.execute(LOADS_QUERY).fetchall()
        (cluster,) = cur.execute(CLUSTER_QUERY).fetchone()
    months = LOAD_SEPARATOR.join(f"{referencia}:{total}" for referencia, total in loads)
    return f"{months}@{cluster}"


class HttpCache:
    """Política de cache da aplicação; API_CACHE_TTL_S=0 desliga."""

    def __init__(self, ttl_s: int) -> None:
        self.ttl_s = ttl_s
        self.version = Lazy(load_data_version)

    @property
    def enabled(self) -> bool:
        return self.ttl_s > 0

    def not_modified(self) -> Response | None:
        """304 se o cliente já tem a resposta desta versão dos dados; senão None."""
        if not self.enabled:
            return None
        # Comparação fraca: o gzip do nginx entrega o ETag como W/"...".
        if request.if_none_match.contains_weak(self.version.get()):
            return Response(status=HTTPStatus.NOT_MODIFIED)
        return None

    def set_headers(self, response: Response) -> Response:
        """after_request: cacheável só 200/404/304 das duas rotas, com a versão já lida."""
        version = self.version.peek()
        if (
            self.enabled
            and version is not None
            and request.endpoint in CACHEABLE_ENDPOINTS
            and response.status_code in CACHEABLE_STATUSES
        ):
            response.headers["Cache-Control"] = f"public, max-age={self.ttl_s}"
            response.set_etag(version)
        else:
            response.headers["Cache-Control"] = NO_STORE
        return response


def init_http_cache(app: Flask) -> None:
    """Liga a política de cache; a versão dos dados só é lida no primeiro uso, no worker."""
    cache = HttpCache(app.config["API_CACHE_TTL_S"])
    app.extensions[EXTENSION_KEY] = cache
    app.after_request(cache.set_headers)


def not_modified() -> Response | None:
    """Para as rotas cacheáveis, logo depois de validar a entrada e antes de abrir conexão.

    Na primeira chamada do worker lê a versão dos dados (pode responder 503 ou 504, como a
    busca). Depois disso, um 304 não toca no banco.
    """
    cache: HttpCache = current_app.extensions[EXTENSION_KEY]
    return cache.not_modified()
