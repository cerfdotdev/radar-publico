"""Testes do ponto de entrada wsgi.py."""

from wsgi import app


def test_wsgi_app_instance():
    """Verifica se a instância WSGI exportada é uma aplicação Flask válida."""
    assert app is not None
    assert app.name == "app"
