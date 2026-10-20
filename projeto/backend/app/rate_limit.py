"""Limites de requisições por IP: acima deles, 429 MUITAS_REQUISICOES com Retry-After.

Há dois: o geral (RATE_LIMIT_REQUESTS), que vale para toda requisição menos o health, e um
menor só para as buscas com 'similar' (RATE_LIMIT_SIMILAR_REQUESTS), a busca mais cara. A
busca parecida conta nos dois, na mesma janela de RATE_LIMIT_WINDOW_S.

A contagem fica na memória de cada worker do Gunicorn (não há armazenamento compartilhado,
como Redis): com N workers, um IP consegue até N × o limite por janela, conforme o Gunicorn
distribui as conexões entre eles.
"""

import math
import threading
import time
from collections.abc import Callable

from flask import Flask, request
from werkzeug.exceptions import TooManyRequests
from werkzeug.middleware.proxy_fix import ProxyFix

import server_settings as s

EXTENSION_KEY = "rate_limiter"
SIMILAR_EXTENSION_KEY = "similar_rate_limiter"
# Só a busca usa 'similar'; no detalhe ele é parâmetro desconhecido (400) e conta só no geral.
SIMILAR_ENDPOINT = "servidores.listar_servidores"
SIMILAR_PARAM = "similar"


class FixedWindowLimiter:
    """Conta requisições por chave em janelas fixas de window_s segundos.

    A memória fica limitada às chaves de uma janela: na virada, as contagens são apagadas.
    """

    def __init__(
        self, limit: int, window_s: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        # O worker gthread atende várias requisições ao mesmo tempo, uma por thread.
        self._lock = threading.Lock()
        self._window: int | None = None
        self._counts: dict[str, int] = {}

    def hit(self, key: str) -> int | None:
        """Conta uma requisição; devolve None se couber no limite, ou em quantos segundos
        a janela vira e a chave pode tentar de novo."""
        now = self._clock()
        window = int(now // self.window_s)
        with self._lock:
            if window != self._window:
                # Janela nova: as contagens antigas não valem mais e a memória não cresce.
                self._window = window
                self._counts.clear()
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
        if count <= self.limit:
            return None
        # Sempre 1 ou mais: now fica antes do fim da janela.
        return math.ceil((window + 1) * self.window_s - now)


def build_limiter(app: Flask, key: str, limit: int) -> FixedWindowLimiter | None:
    """Limitador guardado em app.extensions[key], ou None se o limite é 0 (desligado)."""
    if not limit:
        return None
    limiter = FixedWindowLimiter(limit, app.config["RATE_LIMIT_WINDOW_S"])
    app.extensions[key] = limiter
    return limiter


def enforce(limiter: FixedWindowLimiter, client: str) -> None:
    """Conta a requisição do cliente; acima do limite, 429 com Retry-After."""
    retry_after = limiter.hit(client)
    if retry_after is not None:
        raise TooManyRequests(retry_after=retry_after)


def init_rate_limit(app: Flask) -> None:
    """Liga os limites por IP (0 desliga cada um) e acha o IP real atrás do nginx."""
    hops = app.config["PROXY_HOPS"]
    if hops:
        # O nginx do frontend troca o X-Forwarded-For pelo IP de quem conectou nele. Sem
        # isso, todo usuário da web teria o IP do nginx e dividiria o mesmo limite.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=0)

    general = build_limiter(app, EXTENSION_KEY, app.config["RATE_LIMIT_REQUESTS"])
    similar = build_limiter(app, SIMILAR_EXTENSION_KEY, app.config["RATE_LIMIT_SIMILAR_REQUESTS"])
    if general is None and similar is None:
        return

    @app.before_request
    def limit_by_ip() -> None:
        # O healthcheck do container e o smoke test do CI nunca podem receber 429.
        if request.path == s.HEALTH_PATH:
            return
        # A mesma chave nos dois: o IP do cliente, já corrigido pelo ProxyFix.
        client = request.remote_addr or ""
        if general is not None:
            enforce(general, client)
        # Conta antes da validação, como o geral: o padrão inválido também pesa no limite.
        if (
            similar is not None
            and request.endpoint == SIMILAR_ENDPOINT
            and SIMILAR_PARAM in request.args
        ):
            enforce(similar, client)
