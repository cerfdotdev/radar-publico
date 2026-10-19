"""Configuração da aplicação lida do ambiente: banco de dados e pool de conexões.

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
MIN_SECONDS = 1


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
        "DB_CONNECT_TIMEOUT_S": s.int_from_env(
            "DB_CONNECT_TIMEOUT_S", DEFAULT_CONNECT_TIMEOUT_S, MIN_SECONDS
        ),
    }
