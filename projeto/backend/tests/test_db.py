"""Testes do pool de conexões. Os que usam banco rodam contra o Postgres do CI."""

import socket
import threading
from http import HTTPStatus

import psycopg

from app.db import EXTENSION_KEY, get_db_connection, get_db_pool
from app.errors import BUSY_RETRY_AFTER_S, SERVIDOR_OCUPADO

SHORT_POOL_TIMEOUT_S = 1


def add_select_route(application):
    """Rota de teste que usa uma conexão do pool."""

    @application.get("/api/_select")
    def select_one():
        with get_db_connection() as connection:
            value = connection.execute("SELECT 1").fetchone()[0]
        return {"value": value}

    return application


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_pool_is_created_closed_and_per_app(make_app):
    first, second = make_app(), make_app()
    assert first.extensions[EXTENSION_KEY] is not second.extensions[EXTENSION_KEY]
    assert first.extensions[EXTENSION_KEY].closed


def test_health_does_not_open_the_pool(client, app):
    assert client.get("/api/health").status_code == HTTPStatus.OK
    assert app.extensions[EXTENSION_KEY].closed


def test_first_use_opens_pool_and_queries(make_app, database_url):
    application = add_select_route(make_app(DATABASE_URL=database_url))
    response = application.test_client().get("/api/_select")
    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {"value": 1}
    assert not application.extensions[EXTENSION_KEY].closed


def test_exhausted_pool_returns_503(make_app, database_url):
    application = add_select_route(
        make_app(
            DATABASE_URL=database_url,
            DB_POOL_MIN=1,
            DB_POOL_MAX=1,
            DB_POOL_TIMEOUT_S=SHORT_POOL_TIMEOUT_S,
        )
    )
    holding, release = threading.Event(), threading.Event()

    def hold_only_connection():
        with application.app_context(), get_db_connection():
            holding.set()
            release.wait()

    holder = threading.Thread(target=hold_only_connection)
    holder.start()
    try:
        assert holding.wait(timeout=5)
        response = application.test_client().get("/api/_select")
    finally:
        release.set()
        holder.join()

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.get_json()["error"]["code"] == SERVIDOR_OCUPADO
    assert response.headers["Retry-After"] == str(BUSY_RETRY_AFTER_S)
    # Depois de liberada, a conexão volta ao pool e atende de novo.
    assert application.test_client().get("/api/_select").status_code == HTTPStatus.OK


def test_broken_connection_is_replaced(make_app, database_url):
    application = add_select_route(
        make_app(DATABASE_URL=database_url, DB_POOL_MIN=1, DB_POOL_MAX=1)
    )
    with application.app_context():
        with get_db_connection() as connection:
            backend_pid = connection.info.backend_pid
    with psycopg.connect(database_url, autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(%s)", (backend_pid,))

    response = application.test_client().get("/api/_select")
    assert response.status_code == HTTPStatus.OK


def test_unreachable_database_returns_503_and_health_stays_up(make_app):
    application = add_select_route(
        make_app(
            DATABASE_URL=f"postgresql://radar:radar@127.0.0.1:{free_port()}/radar",
            DB_POOL_TIMEOUT_S=SHORT_POOL_TIMEOUT_S,
        )
    )
    client = application.test_client()
    assert client.get("/api/_select").status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert client.get("/api/health").status_code == HTTPStatus.OK


def test_get_db_pool_is_idempotent(app):
    with app.app_context():
        assert get_db_pool() is get_db_pool()
