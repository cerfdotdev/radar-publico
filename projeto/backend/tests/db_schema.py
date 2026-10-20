"""Schema temporário com as tabelas reais, para os testes que consultam o Postgres do CI."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from itertools import count
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "init" / "01-schema.sql"
_schema_numbers = count()


@contextmanager
def temporary_schema(
    database_url: str, populate: Callable[[psycopg.Connection], None]
) -> Iterator[str]:
    """Schema novo com projeto/db/init/01-schema.sql, preenchido por populate(conn).

    Devolve a URL que usa esse schema pelo search_path; o schema é apagado ao sair.
    """
    schema = f"api_teste_{os.getpid()}_{next(_schema_numbers)}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        populate(conn)
    try:
        yield make_conninfo(database_url, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
