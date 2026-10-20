"""Limite de requisições por IP: acima dele, 429 MUITAS_REQUISICOES com Retry-After.

A contagem fica na memória de cada worker do Gunicorn (não há armazenamento compartilhado,
como Redis): com N workers, um IP consegue até N × RATE_LIMIT_REQUESTS por janela,
conforme o Gunicorn distribui as conexões entre eles.
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


class FixedWindowLimiter:
    """Conta requisições por chave em janelas fixas de window_s segundos."""

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


def init_rate_limit(app: Flask) -> None:
    """Liga o limite por IP (RATE_LIMIT_REQUESTS=0 desliga) e acha o IP real atrás do nginx."""
    hops = app.config["PROXY_HOPS"]
    if hops:
        # O nginx do frontend troca o X-Forwarded-For pelo IP de quem conectou nele. Sem
        # isso, todo usuário da web teria o IP do nginx e dividiria o mesmo limite.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=0)

    limit = app.config["RATE_LIMIT_REQUESTS"]
    if not limit:
        return
    limiter = FixedWindowLimiter(limit, app.config["RATE_LIMIT_WINDOW_S"])
    app.extensions[EXTENSION_KEY] = limiter

    @app.before_request
    def limit_by_ip() -> None:
        # O healthcheck do container e o smoke test do CI nunca podem receber 429.
        if request.path == s.HEALTH_PATH:
            return
        retry_after = limiter.hit(request.remote_addr or "")
        if retry_after is not None:
            raise TooManyRequests(retry_after=retry_after)
