"""Testes do ponto de entrada wsgi.py."""

from http import HTTPStatus

from flask import Flask

from wsgi import app


def test_wsgi_exports_working_flask_app():
    assert isinstance(app, Flask)
    response = app.test_client().get("/api/health")
    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {"status": "ok"}
