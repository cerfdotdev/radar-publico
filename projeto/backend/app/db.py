"""Pool de conexões com o PostgreSQL (psycopg_pool), um por processo de worker.

O pool é criado fechado em create_app() e aberto no primeiro uso. Assim ele nasce
dentro do worker do Gunicorn, depois do fork: threads e sockets do pool não são
compartilhados entre processos, inclusive com --preload.
"""

import atexit
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial

from flask import Flask, current_app
from psycopg import Connection
from psycopg_pool import ConnectionPool

EXTENSION_KEY = "db_pool"
POOL_NAME = "radar-api"
# set_config aceita parâmetro (SET não aceita); false: vale para a sessão, não só a transação.
STATEMENT_TIMEOUT_SQL = "SELECT set_config('statement_timeout', %s, false)"


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL não foi definida."""


def set_statement_timeout(connection: Connection, timeout_s: int) -> None:
    """Limita o tempo de cada consulta da conexão; a que passar é cancelada (504)."""
    connection.execute(STATEMENT_TIMEOUT_SQL, (f"{timeout_s}s",))
    # O pool recusa conexão com transação aberta: fecha a que o SELECT abriu.
    connection.commit()


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
        # Toda conexão nova sai com o statement_timeout da aplicação, sem depender do usuário
        # do banco (05-usuario-api.sh) e sem trocar as options que vierem na DATABASE_URL.
        configure=partial(set_statement_timeout, timeout_s=app.config["DB_STATEMENT_TIMEOUT_S"]),
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
