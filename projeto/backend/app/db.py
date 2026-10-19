"""Pool de conexões com o PostgreSQL (psycopg_pool), um por processo de worker.

O pool é criado fechado em create_app() e aberto no primeiro uso. Assim ele nasce
dentro do worker do Gunicorn, depois do fork: threads e sockets do pool não são
compartilhados entre processos, inclusive com --preload.
"""

import atexit
from collections.abc import Iterator
from contextlib import contextmanager

from flask import Flask, current_app
from psycopg import Connection
from psycopg_pool import ConnectionPool

EXTENSION_KEY = "db_pool"
POOL_NAME = "radar-api"


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL não foi definida."""


def init_db(app: Flask) -> None:
    """Cria o pool (ainda fechado) a partir da configuração da aplicação."""
    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL não definida. Ex.: postgresql://usuario:senha@host:5432/banco"
        )

    pool = ConnectionPool(
        conninfo=database_url,
        min_size=app.config["DB_POOL_MIN"],
        max_size=app.config["DB_POOL_MAX"],
        timeout=app.config["DB_POOL_TIMEOUT_S"],
        # Descarta conexões quebradas (ex.: banco reiniciado) antes de entregá-las.
        check=ConnectionPool.check_connection,
        kwargs={"connect_timeout": app.config["DB_CONNECT_TIMEOUT_S"]},
        name=POOL_NAME,
        open=False,
    )
    app.extensions[EXTENSION_KEY] = pool
    atexit.register(pool.close)


def get_db_pool(app: Flask | None = None) -> ConnectionPool:
    """Devolve o pool da aplicação, abrindo-o no primeiro uso."""
    pool: ConnectionPool = (app or current_app).extensions[EXTENSION_KEY]
    # Seguro chamar várias vezes e de várias threads; não espera as conexões iniciais.
    pool.open()
    return pool


@contextmanager
def get_db_connection() -> Iterator[Connection]:
    """Empresta uma conexão do pool; ela volta ao pool ao sair do bloco, mesmo com erro."""
    with get_db_pool().connection() as connection:
        yield connection


def close_db_pool(app: Flask) -> None:
    """Fecha o pool da aplicação (usado no encerramento e nos testes)."""
    app.extensions[EXTENSION_KEY].close()
