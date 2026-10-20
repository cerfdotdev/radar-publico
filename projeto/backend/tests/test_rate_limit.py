"""Testes dos limites de requisições por IP, o geral e o de 'similar' (429 MUITAS_REQUISICOES)."""

import threading
from http import HTTPStatus

import pytest

import server_settings as s
from app import config as c
from app.errors import HTTP_ERRORS
from app.rate_limit import EXTENSION_KEY, SIMILAR_EXTENSION_KEY, FixedWindowLimiter

LIMIT = 2
WINDOW_S = 60
# Sem filtro, a busca responde 400 antes de consultar o banco: estes testes não usam Postgres.
NO_DB_PATH = "/api/servidores"
# Busca parecida que também responde 400 sem banco: o parâmetro desconhecido é conferido antes.
SIMILAR_NO_DB = {"similar": "%MARIA%", "bogus": "1"}
# O limite geral fica bem acima do de 'similar' nos testes do limite de 'similar'.
GENERAL_LIMIT = 100
# Endereços de documentação (RFC 5737): o nginx na rede do compose e dois clientes.
NGINX_ADDR = "192.0.2.10"
CLIENT_A = "203.0.113.1"
CLIENT_B = "203.0.113.2"
RATE_LIMIT_ENV = [
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_SIMILAR_REQUESTS",
    "RATE_LIMIT_WINDOW_S",
    "PROXY_HOPS",
]


class FakeClock:
    """Relógio controlado pelo teste."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def via_nginx(client, client_ip, path=NO_DB_PATH, query=None):
    """Requisição como o nginx repassa: vem do IP dele, com o do cliente no X-Forwarded-For."""
    return client.get(
        path,
        query_string=query,
        environ_base={"REMOTE_ADDR": NGINX_ADDR},
        headers={"X-Forwarded-For": client_ip},
    )


def similar_via_nginx(client, client_ip, path=NO_DB_PATH):
    return via_nginx(client, client_ip, path, SIMILAR_NO_DB)


def direct(client, client_ip):
    """Requisição direto na porta do backend, sem proxy."""
    return client.get(NO_DB_PATH, environ_base={"REMOTE_ADDR": client_ip})


def use_up_limit(request_as, client, client_ip):
    for _ in range(LIMIT):
        assert request_as(client, client_ip).status_code == HTTPStatus.BAD_REQUEST


@pytest.fixture
def limited(make_app):
    return make_app(RATE_LIMIT_REQUESTS=LIMIT, RATE_LIMIT_WINDOW_S=WINDOW_S).test_client()


@pytest.fixture
def similar_limited(make_app):
    return make_app(
        RATE_LIMIT_REQUESTS=GENERAL_LIMIT,
        RATE_LIMIT_SIMILAR_REQUESTS=LIMIT,
        RATE_LIMIT_WINDOW_S=WINDOW_S,
    ).test_client()


@pytest.fixture
def env(monkeypatch):
    for var in RATE_LIMIT_ENV:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_limiter_counts_per_key_and_reopens_in_next_window():
    elapsed_s = 10
    clock = FakeClock(elapsed_s)
    limiter = FixedWindowLimiter(LIMIT, WINDOW_S, clock)
    assert [limiter.hit("a") for _ in range(LIMIT)] == [None] * LIMIT
    assert limiter.hit("a") == WINDOW_S - elapsed_s
    assert limiter.hit("b") is None
    clock.now = WINDOW_S
    assert limiter.hit("a") is None


def test_retry_after_rounds_up_to_whole_seconds():
    clock = FakeClock(WINDOW_S - 0.25)
    limiter = FixedWindowLimiter(1, WINDOW_S, clock)
    limiter.hit("a")
    assert limiter.hit("a") == 1


def test_limiter_is_exact_with_concurrent_threads():
    threads, hits_per_thread, limit = 8, 50, 100
    limiter = FixedWindowLimiter(limit, WINDOW_S, FakeClock(0))
    allowed = []

    def hit_many():
        for _ in range(hits_per_thread):
            allowed.append(limiter.hit("a") is None)

    workers = [threading.Thread(target=hit_many) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert allowed.count(True) == limit


def test_over_limit_returns_429_envelope_with_retry_after(limited):
    use_up_limit(via_nginx, limited, CLIENT_A)
    response = via_nginx(limited, CLIENT_A)
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    code, message = HTTP_ERRORS[HTTPStatus.TOO_MANY_REQUESTS]
    assert code == "MUITAS_REQUISICOES"
    assert response.get_json() == {"error": {"code": code, "message": message}}
    assert 1 <= int(response.headers["Retry-After"]) <= WINDOW_S


def test_health_is_never_limited(limited):
    use_up_limit(via_nginx, limited, CLIENT_A)
    for _ in range(LIMIT + 1):
        assert via_nginx(limited, CLIENT_A, s.HEALTH_PATH).status_code == HTTPStatus.OK


def test_detail_route_is_limited_too(limited):
    # Id inválido responde 400 sem consultar o banco, mas conta no limite como a busca.
    detail_path = "/api/servidores/abc"
    for _ in range(LIMIT):
        assert via_nginx(limited, CLIENT_A, detail_path).status_code == HTTPStatus.BAD_REQUEST
    assert via_nginx(limited, CLIENT_A, detail_path).status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_clients_behind_nginx_have_their_own_limit(limited):
    use_up_limit(via_nginx, limited, CLIENT_A)
    assert via_nginx(limited, CLIENT_A).status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert via_nginx(limited, CLIENT_B).status_code == HTTPStatus.BAD_REQUEST


def test_direct_clients_are_limited_by_their_address(limited):
    use_up_limit(direct, limited, CLIENT_A)
    assert direct(limited, CLIENT_A).status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert direct(limited, CLIENT_B).status_code == HTTPStatus.BAD_REQUEST


def test_forwarded_for_is_ignored_without_proxy_hops(make_app):
    client = make_app(RATE_LIMIT_REQUESTS=LIMIT, PROXY_HOPS=0).test_client()
    use_up_limit(via_nginx, client, CLIENT_A)
    # Todos chegam do mesmo endereço (o do nginx) e dividem o limite.
    assert via_nginx(client, CLIENT_B).status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_zero_disables_the_limit(make_app):
    application = make_app(RATE_LIMIT_REQUESTS=0)
    assert EXTENSION_KEY not in application.extensions
    client = application.test_client()
    for _ in range(c.DEFAULT_RATE_LIMIT_REQUESTS + 1):
        assert via_nginx(client, CLIENT_A).status_code == HTTPStatus.BAD_REQUEST


def test_similar_has_a_tighter_limit_with_the_same_envelope(similar_limited):
    use_up_limit(similar_via_nginx, similar_limited, CLIENT_A)
    response = similar_via_nginx(similar_limited, CLIENT_A)
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    code, message = HTTP_ERRORS[HTTPStatus.TOO_MANY_REQUESTS]
    assert response.get_json() == {"error": {"code": code, "message": message}}
    assert 1 <= int(response.headers["Retry-After"]) <= WINDOW_S
    # O limite geral continua com folga para as outras buscas do mesmo IP.
    assert via_nginx(similar_limited, CLIENT_A).status_code == HTTPStatus.BAD_REQUEST


def test_similar_limit_is_per_client_behind_nginx(similar_limited):
    use_up_limit(similar_via_nginx, similar_limited, CLIENT_A)
    assert similar_via_nginx(similar_limited, CLIENT_A).status_code == (
        HTTPStatus.TOO_MANY_REQUESTS
    )
    assert similar_via_nginx(similar_limited, CLIENT_B).status_code == HTTPStatus.BAD_REQUEST


def test_similar_limit_ignores_forwarded_for_without_proxy_hops(make_app):
    client = make_app(
        RATE_LIMIT_REQUESTS=GENERAL_LIMIT, RATE_LIMIT_SIMILAR_REQUESTS=LIMIT, PROXY_HOPS=0
    ).test_client()
    use_up_limit(similar_via_nginx, client, CLIENT_A)
    assert similar_via_nginx(client, CLIENT_B).status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_only_similar_searches_count_in_the_similar_limit(similar_limited):
    for _ in range(LIMIT + 1):
        assert via_nginx(similar_limited, CLIENT_A).status_code == HTTPStatus.BAD_REQUEST
        # No detalhe, 'similar' é só um parâmetro desconhecido.
        detail = similar_via_nginx(similar_limited, CLIENT_A, "/api/servidores/1")
        assert detail.status_code == HTTPStatus.BAD_REQUEST
    use_up_limit(similar_via_nginx, similar_limited, CLIENT_A)


def test_similar_limit_works_with_the_general_limit_off(make_app):
    application = make_app(RATE_LIMIT_REQUESTS=0, RATE_LIMIT_SIMILAR_REQUESTS=LIMIT)
    assert EXTENSION_KEY not in application.extensions
    client = application.test_client()
    use_up_limit(similar_via_nginx, client, CLIENT_A)
    assert similar_via_nginx(client, CLIENT_A).status_code == HTTPStatus.TOO_MANY_REQUESTS
    for _ in range(c.DEFAULT_RATE_LIMIT_REQUESTS + 1):
        assert via_nginx(client, CLIENT_A).status_code == HTTPStatus.BAD_REQUEST


def test_zero_disables_the_similar_limit(make_app):
    application = make_app(RATE_LIMIT_REQUESTS=GENERAL_LIMIT, RATE_LIMIT_SIMILAR_REQUESTS=0)
    assert SIMILAR_EXTENSION_KEY not in application.extensions
    client = application.test_client()
    for _ in range(c.DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS + 1):
        assert similar_via_nginx(client, CLIENT_A).status_code == HTTPStatus.BAD_REQUEST


def test_both_limits_off_installs_no_hook(make_app):
    application = make_app(RATE_LIMIT_REQUESTS=0, RATE_LIMIT_SIMILAR_REQUESTS=0)
    assert EXTENSION_KEY not in application.extensions
    assert SIMILAR_EXTENSION_KEY not in application.extensions
    assert not application.before_request_funcs


def test_defaults(env):
    config = c.load_config()
    assert config["RATE_LIMIT_REQUESTS"] == c.DEFAULT_RATE_LIMIT_REQUESTS
    assert config["RATE_LIMIT_SIMILAR_REQUESTS"] == c.DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS
    assert c.DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS < c.DEFAULT_RATE_LIMIT_REQUESTS
    assert config["RATE_LIMIT_WINDOW_S"] == c.DEFAULT_RATE_LIMIT_WINDOW_S
    assert config["PROXY_HOPS"] == c.DEFAULT_PROXY_HOPS


def test_values_come_from_environment(env, make_app):
    env.setenv("RATE_LIMIT_REQUESTS", "5")
    env.setenv("RATE_LIMIT_SIMILAR_REQUESTS", "3")
    env.setenv("RATE_LIMIT_WINDOW_S", "30")
    env.setenv("PROXY_HOPS", "0")
    application = make_app()
    limiter = application.extensions[EXTENSION_KEY]
    assert (limiter.limit, limiter.window_s) == (5, 30)
    similar = application.extensions[SIMILAR_EXTENSION_KEY]
    assert (similar.limit, similar.window_s) == (3, 30)
    assert application.config["PROXY_HOPS"] == 0


@pytest.mark.parametrize("raw", ["abc", "-1"])
def test_invalid_values_fall_back_to_defaults(env, raw):
    for var in RATE_LIMIT_ENV:
        env.setenv(var, raw)
    config = c.load_config()
    assert config["RATE_LIMIT_REQUESTS"] == c.DEFAULT_RATE_LIMIT_REQUESTS
    assert config["RATE_LIMIT_SIMILAR_REQUESTS"] == c.DEFAULT_RATE_LIMIT_SIMILAR_REQUESTS
    assert config["RATE_LIMIT_WINDOW_S"] == c.DEFAULT_RATE_LIMIT_WINDOW_S
    assert config["PROXY_HOPS"] == c.DEFAULT_PROXY_HOPS
