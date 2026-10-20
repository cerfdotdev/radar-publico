"""Configuração da aplicação lida do ambiente: banco, pool de conexões, limites por IP e cache.

Os valores são lidos quando create_app() roda (e não na importação do módulo), para que
o ambiente de cada processo, e o dos testes, seja respeitado.
"""

import os

import server_settings as s

# O usuário radar_api aceita no máximo 50 conexões (projeto/db/init/05-usuario-api.sh).
# A folga fica para psql, healthcheck do banco e manutenção.
DB_ROLE_CONNECTION_LIMIT = 50
DB_CONNECTION_HEADROOM = 5
DB_CONNECTION_BUDGET = DB_ROLE_CONNECTION_LIMIT - DB_CONNECTION_HEADROOM

DEFAULT_POOL_MIN = 1
MIN_POOL_MIN = 0
MIN_POOL_MAX = 1
# Com o pool cheio, é melhor responder 503 rápido do que segurar a requisição.
DEFAULT_POOL_TIMEOUT_S = 3
DEFAULT_CONNECT_TIMEOUT_S = 5
# Tempo máximo de cada consulta (statement_timeout). Fica abaixo dos 15 s do nginx
# (proxy_read_timeout em projeto/frontend/nginx.conf), para a API responder 504 antes dele.
DEFAULT_STATEMENT_TIMEOUT_S = 5
MIN_SECONDS = 1

# Limite por IP (app/rate_limit.py). A tela só busca ao enviar o formulário ou trocar de
# página: uma pessoa fica longe de 1 por segundo, e um script em laço leva 429 logo.
DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_S = 60
# Limite próprio das buscas com 'similar', além do geral: é a busca mais cara (até 0,8 s com
# padrões comuns como %MARIA%, docs/carga.md, cenário 4). Uma pessoa faz poucas por minuto:
# digita o padrão, olha a lista e ajusta; o site ainda sugere um padrão parecido quando o nome
# exato não acha ninguém, uma busca a mais. Com 2 workers, um IP faz até 20 por minuto, cerca
# de 16 s de thread a 0,8 s cada, de 480 (8 threads × 60 s): o resto fica para os outros.
DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS = 10
# Proxies na frente do backend que trocam o X-Forwarded-For: o nginx do frontend.
DEFAULT_PROXY_HOPS = 1

# Por quanto tempo o navegador e o nginx do frontend reusam uma resposta 200 ou 404 da busca
# e do detalhe (app/http_cache.py). Os dados só mudam ao recarregar a base; vencido o prazo,
# o nginx revalida pelo ETag e o backend responde 304 sem refazer a busca. Curto para que,
# depois de uma recarga, nada antigo dure mais que isso no navegador.
DEFAULT_API_CACHE_TTL_S = 60


def pool_max_for(workers: int, requested: int) -> int:
    """Limita o pool por worker para que workers × pool caiba no orçamento do banco."""
    per_worker = max(MIN_POOL_MAX, DB_CONNECTION_BUDGET // workers)
    if requested > per_worker:
        s.log.warning(
            "DB_POOL_MAX=%d com %d workers passaria de %d conexões; usando %d por worker",
            requested,
            workers,
            DB_CONNECTION_BUDGET,
            per_worker,
        )
        return per_worker
    return requested


def load_config() -> dict:
    """Monta a configuração do banco a partir do ambiente."""
    workers = s.int_from_env("GUNICORN_WORKERS", s.DEFAULT_WORKERS, s.MIN_WORKERS)
    threads = s.int_from_env("GUNICORN_THREADS", s.DEFAULT_THREADS, s.MIN_THREADS)

    # Uma conexão por thread do worker: mais que isso nunca seria usado ao mesmo tempo.
    requested_max = s.int_from_env("DB_POOL_MAX", threads, MIN_POOL_MAX)
    pool_max = pool_max_for(workers, requested_max)
    pool_min = min(s.int_from_env("DB_POOL_MIN", DEFAULT_POOL_MIN, MIN_POOL_MIN), pool_max)

    return {
        "DATABASE_URL": os.getenv("DATABASE_URL", "").strip() or None,
        "DB_POOL_MIN": pool_min,
        "DB_POOL_MAX": pool_max,
        "DB_POOL_TIMEOUT_S": s.int_from_env(
            "DB_POOL_TIMEOUT_S", DEFAULT_POOL_TIMEOUT_S, MIN_SECONDS
        ),
        "DB_STATEMENT_TIMEOUT_S": s.int_from_env(
            "DB_STATEMENT_TIMEOUT_S", DEFAULT_STATEMENT_TIMEOUT_S, MIN_SECONDS
        ),
        "DB_CONNECT_TIMEOUT_S": s.int_from_env(
            "DB_CONNECT_TIMEOUT_S", DEFAULT_CONNECT_TIMEOUT_S, MIN_SECONDS
        ),
        # 0 desliga o limite (ex.: teste de carga) ou deixa de confiar no X-Forwarded-For.
        "RATE_LIMIT_REQUESTS": s.int_from_env(
            "RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS, s.MIN_COUNT_OFF
        ),
        # Na mesma janela do limite geral; 0 desliga só este.
        "RATE_LIMIT_SIMILAR_REQUESTS": s.int_from_env(
            "RATE_LIMIT_SIMILAR_REQUESTS", DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS, s.MIN_COUNT_OFF
        ),
        "RATE_LIMIT_WINDOW_S": s.int_from_env(
            "RATE_LIMIT_WINDOW_S", DEFAULT_RATE_LIMIT_WINDOW_S, MIN_SECONDS
        ),
        "PROXY_HOPS": s.int_from_env("PROXY_HOPS", DEFAULT_PROXY_HOPS, s.MIN_COUNT_OFF),
        # 0 desliga o cache (ex.: o teste de carga sem cache); o nginx lê a mesma variável.
        "API_CACHE_TTL_S": s.int_from_env(
            "API_CACHE_TTL_S", DEFAULT_API_CACHE_TTL_S, s.MIN_COUNT_OFF
        ),
    }
