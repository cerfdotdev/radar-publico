"""Testes do healthcheck do container."""

import threading
from http import HTTPStatus
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

import healthcheck
import server_settings as s


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def wsgi_app_with_status(status: HTTPStatus):
    def application(environ, start_response):
        start_response(f"{status.value} {status.phrase}", [("Content-Type", "text/plain")])
        return [b""]

    return application


@pytest.fixture
def serve(monkeypatch):
    """Sobe um servidor local numa porta livre e aponta o healthcheck para ele."""
    servers = []

    def start(status: HTTPStatus):
        server = make_server(
            s.HEALTHCHECK_HOST, 0, wsgi_app_with_status(status), handler_class=QuietHandler
        )
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        monkeypatch.setenv("GUNICORN_PORT", str(server.server_port))

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_healthy_api_exits_ok(serve):
    serve(HTTPStatus.OK)
    assert healthcheck.check() == healthcheck.EXIT_OK


def test_error_status_exits_fail(serve):
    serve(HTTPStatus.SERVICE_UNAVAILABLE)
    assert healthcheck.check() == healthcheck.EXIT_FAIL


def test_nothing_listening_exits_fail(monkeypatch):
    with make_server(s.HEALTHCHECK_HOST, 0, wsgi_app_with_status(HTTPStatus.OK)) as server:
        free_port = server.server_port
    monkeypatch.setenv("GUNICORN_PORT", str(free_port))
    assert healthcheck.check() == healthcheck.EXIT_FAIL


def test_health_url_uses_configured_port(monkeypatch):
    monkeypatch.setenv("GUNICORN_PORT", "8123")
    assert s.health_url() == (s.HEALTHCHECK_HOST, 8123, s.HEALTH_PATH)
