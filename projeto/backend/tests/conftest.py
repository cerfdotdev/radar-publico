"""Fixtures para os testes do backend."""

import os

import psycopg
import pytest

# O mesmo banco vazio que o CI sobe como serviço (.github/workflows/ci.yml).
# Precisa estar definido antes de importar wsgi.py, que cria a aplicação.
CI_DATABASE_URL = "postgresql://radar:radar@localhost:5432/radar_test"
os.environ.setdefault("DATABASE_URL", CI_DATABASE_URL)

from app import create_app  # noqa: E402
from app.db import close_db_pool  # noqa: E402

PROBE_CONNECT_TIMEOUT_S = 2


@pytest.fixture
def make_app():
    """Cria aplicações de teste e fecha os pools delas ao final."""
    apps = []

    def factory(**overrides):
        application = create_app({"TESTING": True, **overrides})
        apps.append(application)
        return application

    yield factory
    for application in apps:
        close_db_pool(application)


@pytest.fixture
def app(make_app):
    """Aplicação Flask configurada para testes."""
    return make_app()


@pytest.fixture
def client(app):
    """Cliente de teste do Flask."""
    return app.test_client()


@pytest.fixture(scope="session")
def database_url():
    """URL de um Postgres acessível; pula os testes de banco se não houver."""
    url = os.environ["DATABASE_URL"]
    try:
        psycopg.connect(url, connect_timeout=PROBE_CONNECT_TIMEOUT_S).close()
    except psycopg.OperationalError as error:
        pytest.skip(f"Postgres indisponível em DATABASE_URL: {error}")
    return url
