"""Testes das respostas de erro em JSON (docs/api.md)."""

from http import HTTPStatus

import pytest
from werkzeug.exceptions import BadRequest, Gone

from app import create_app
from app.errors import ERRO_INTERNO, INTERNAL_ERROR_MESSAGE, error_response


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/nao-existe")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.is_json
    assert response.get_json()["error"]["code"] == "ROTA_INEXISTENTE"


def test_wrong_method_returns_json_405_with_allow(client):
    response = client.post("/api/health")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.get_json()["error"]["code"] == "METODO_NAO_PERMITIDO"
    assert "GET" in response.headers["Allow"]


def test_static_route_is_disabled(client):
    response = client.get("/static/x.css")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.is_json


@pytest.fixture
def app_with_failing_routes():
    app = create_app({"TESTING": True})

    @app.get("/api/_falha")
    def fail():
        raise RuntimeError("detalhe interno que não pode vazar")

    @app.get("/api/_ruim")
    def bad():
        raise BadRequest()

    @app.get("/api/_sumiu")
    def gone():
        raise Gone()

    return app


def test_unexpected_error_returns_generic_500(app_with_failing_routes):
    response = app_with_failing_routes.test_client().get("/api/_falha")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    body = response.get_json()
    assert body == {"error": {"code": ERRO_INTERNO, "message": INTERNAL_ERROR_MESSAGE}}
    assert "detalhe interno" not in response.get_data(as_text=True)


def test_bad_request_maps_to_parametro_invalido(app_with_failing_routes):
    response = app_with_failing_routes.test_client().get("/api/_ruim")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"]["code"] == "PARAMETRO_INVALIDO"


def test_unmapped_http_error_keeps_status(app_with_failing_routes):
    response = app_with_failing_routes.test_client().get("/api/_sumiu")
    assert response.status_code == HTTPStatus.GONE
    assert response.get_json()["error"]["code"] == ERRO_INTERNO


def test_json_keeps_accents_unescaped(app):
    with app.app_context():
        response, status = error_response("UF_INVALIDA", "UF 'XX' não existe.", 400)
    assert status == HTTPStatus.BAD_REQUEST
    raw = response.get_data(as_text=True)
    assert "não" in raw
    assert "\\u00e3" not in raw
