"""Fixtures para os testes do backend."""

import pytest

from app import create_app


@pytest.fixture
def app():
    """Cria uma instância da aplicação Flask configurada para testes."""
    application = create_app({"TESTING": True})
    return application


@pytest.fixture
def client(app):
    """Cliente de teste do Flask."""
    return app.test_client()
