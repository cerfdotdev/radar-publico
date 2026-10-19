"""Gerenciamento de conexões com PostgreSQL usando psycopg-pool."""

from collections.abc import Generator
from contextlib import contextmanager

from flask import Flask
from psycopg import Connection
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def init_db(app: Flask) -> None:
    """Inicializa o pool de conexões com base na configuração da aplicação."""
    global _pool
    db_url = app.config.get("DATABASE_URL")
    min_size = app.config.get("DB_POOL_MIN", 1)
    max_size = app.config.get("DB_POOL_MAX", 10)
    timeout = app.config.get("DB_POOL_TIMEOUT", 30.0)

    _pool = ConnectionPool(
        conninfo=db_url,
        min_size=min_size,
        max_size=max_size,
        timeout=timeout,
        open=False,
    )
    app.extensions["db_pool"] = _pool


def get_db_pool() -> ConnectionPool:
    """Retorna o pool de conexões ativo."""
    if _pool is None:
        raise RuntimeError("Pool de banco de dados não inicializado.")
    return _pool


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """Obtém uma conexão do pool dentro de um context manager."""
    pool = get_db_pool()
    with pool.connection() as conn:
        yield conn


def close_db_pool() -> None:
    """Fecha o pool de conexões."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
