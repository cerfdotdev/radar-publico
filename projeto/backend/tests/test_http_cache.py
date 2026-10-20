"""Cabeçalhos de cache da busca e do detalhe (app/http_cache.py, docs/api.md "Cache")."""

import re
import socket
from contextlib import contextmanager
from decimal import Decimal
from http import HTTPStatus

import psycopg
import pytest
from psycopg.errors import QueryCanceled
from psycopg_pool import PoolTimeout

import server_settings as s
from app import config as c
from app.http_cache import EXTENSION_KEY, NO_STORE, load_data_version
from app.routes import servidores
from tests.db_schema import temporary_schema

TTL_S = 30
PUBLIC = f"public, max-age={TTL_S}"
ACTIVE_MONTH, RETIRED_MONTH = "2026-08", "2026-05"
# (nome, situacao, uf, referencia): dois meses de carga, como a base real.
SERVIDORES = [
    ("MARIA DA SILVA", "ativo", "DF", ACTIVE_MONTH),
    ("JOSE CARLOS", "ativo", "RJ", ACTIVE_MONTH),
    ("ANA COSTA", "aposentado", None, RETIRED_MONTH),
]
VERSION_PATTERN = re.compile(rf"{RETIRED_MONTH}:1\+{ACTIVE_MONTH}:2@\d+")
SEARCH = "/api/servidores"
FOUND = {"uf": "DF"}
NOT_FOUND_QUERIES = [
    {"nome": "FULANO DE TAL"},
    {"cargo": "ASTRONAUTA"},
    {"orgao": "NASA"},
    {"uf": "DF", "per_page": 1, "page": 2},
    {"uf": "DF", "situacao": "aposentado"},
]
CACHE_ENV = ["API_CACHE_TTL_S"]
SHORT_POOL_TIMEOUT_S = 1


def populate(conn) -> None:
    conn.execute("INSERT INTO orgao (nome, sigla) VALUES ('MINISTERIO DA SAUDE', 'MS')")
    conn.execute("INSERT INTO cargo (nome) VALUES ('MEDICO')")
    conn.cursor().executemany(
        """
        INSERT INTO servidor (nome, situacao, cargo_id, orgao_id, uf, valor, referencia)
        VALUES (%s, %s, (SELECT id FROM cargo), (SELECT id FROM orgao), %s, %s, %s)
        """,
        [(nome, sit, uf, Decimal("1000.00"), ref) for nome, sit, uf, ref in SERVIDORES],
    )


@pytest.fixture(scope="module")
def schema_url(database_url):
    with temporary_schema(database_url, populate) as url:
        yield url


@pytest.fixture
def app(make_app, schema_url):
    return make_app(DATABASE_URL=schema_url, API_CACHE_TTL_S=TTL_S)


@pytest.fixture
def api(app):
    return app.test_client()


@pytest.fixture
def version(app) -> str:
    with app.app_context():
        return load_data_version()


def detail_path(api) -> str:
    [item] = api.get(SEARCH, query_string=FOUND).get_json()["data"]
    return f"{SEARCH}/{item['id']}"


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def assert_cacheable(response, version: str) -> None:
    assert response.headers["Cache-Control"] == PUBLIC
    assert response.headers["ETag"] == f'"{version}"'


def assert_not_stored(response) -> None:
    assert response.headers["Cache-Control"] == NO_STORE
    assert "ETag" not in response.headers


@contextmanager
def failing_search(monkeypatch, error: Exception):
    """A conexão da busca (não a da versão dos dados) levanta o erro."""

    @contextmanager
    def connection():
        raise error
        yield  # pragma: no cover

    monkeypatch.setattr(servidores, "get_db_connection", connection)
    yield


# --- Versão dos dados ---


def test_version_has_load_months_counts_and_cluster(version):
    assert VERSION_PATTERN.fullmatch(version), version


def test_version_changes_when_the_data_changes(app, schema_url, version):
    with psycopg.connect(schema_url, autocommit=True) as conn:
        conn.execute("UPDATE servidor SET referencia = '2026-09' WHERE nome = 'JOSE CARLOS'")
    try:
        with app.app_context():
            assert load_data_version() != version
    finally:
        with psycopg.connect(schema_url, autocommit=True) as conn:
            conn.execute(
                "UPDATE servidor SET referencia = %s WHERE nome = 'JOSE CARLOS'", (ACTIVE_MONTH,)
            )


def test_version_is_read_once_per_worker(app, api):
    cache = app.extensions[EXTENSION_KEY]
    assert cache.version.peek() is None
    api.get(SEARCH, query_string=FOUND)
    first = cache.version.peek()
    api.get(SEARCH, query_string={"nome": "FULANO DE TAL"})
    assert cache.version.peek() is first


# --- Cabeçalhos por status ---


def test_search_200_is_public_with_etag(api, version):
    response = api.get(SEARCH, query_string=FOUND)
    assert response.status_code == HTTPStatus.OK
    assert_cacheable(response, version)


def test_detail_200_is_public_with_etag(api, version):
    response = api.get(detail_path(api))
    assert response.status_code == HTTPStatus.OK
    assert_cacheable(response, version)


@pytest.mark.parametrize("query", NOT_FOUND_QUERIES)
def test_search_404_is_public_with_etag(api, version, query):
    response = api.get(SEARCH, query_string=query)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert_cacheable(response, version)


def test_detail_404_is_public_with_etag(api, version):
    response = api.get(f"{SEARCH}/999999")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert_cacheable(response, version)


@pytest.mark.parametrize(
    "path",
    [
        f"{SEARCH}?uf=XX",
        f"{SEARCH}?nome=a",
        SEARCH,
        f"{SEARCH}/abc",
        f"{SEARCH}/1?x=1",
    ],
)
def test_400_is_never_stored(api, path):
    response = api.get(path)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert_not_stored(response)


def test_429_is_never_stored(make_app, schema_url):
    api = make_app(DATABASE_URL=schema_url, API_CACHE_TTL_S=TTL_S, RATE_LIMIT_REQUESTS=1)
    client = api.test_client()
    assert client.get(SEARCH, query_string=FOUND).status_code == HTTPStatus.OK
    response = client.get(SEARCH, query_string=FOUND)
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert_not_stored(response)


def test_503_when_the_version_cannot_be_read_is_never_stored(make_app):
    application = make_app(
        DATABASE_URL=f"postgresql://radar:radar@127.0.0.1:{unused_port()}/radar",
        DB_POOL_TIMEOUT_S=SHORT_POOL_TIMEOUT_S,
        API_CACHE_TTL_S=TTL_S,
    )
    response = application.test_client().get(SEARCH, query_string=FOUND)
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert_not_stored(response)
    assert application.extensions[EXTENSION_KEY].version.peek() is None


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (PoolTimeout("pool cheio"), HTTPStatus.SERVICE_UNAVAILABLE),
        (QueryCanceled("statement timeout"), HTTPStatus.GATEWAY_TIMEOUT),
        (RuntimeError("falha inesperada"), HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
@pytest.mark.parametrize("path", [SEARCH, f"{SEARCH}/1"])
def test_5xx_of_cacheable_routes_is_never_stored(api, monkeypatch, error, status, path):
    with failing_search(monkeypatch, error):
        response = api.get(path, query_string=FOUND if path == SEARCH else None)
    assert response.status_code == status
    assert_not_stored(response)


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("get", s.HEALTH_PATH, HTTPStatus.OK),
        ("get", "/api/nao-existe", HTTPStatus.NOT_FOUND),
        ("get", f"{SEARCH}/1/extra", HTTPStatus.NOT_FOUND),
        ("post", SEARCH, HTTPStatus.METHOD_NOT_ALLOWED),
    ],
)
def test_other_routes_are_never_stored(api, method, path, status):
    response = getattr(api, method)(path)
    assert response.status_code == status
    assert_not_stored(response)


# --- ETag e 304 ---


@pytest.mark.parametrize("if_none_match", ['"{v}"', 'W/"{v}"', '"outro", W/"{v}"', "*"])
def test_matching_if_none_match_gets_304(api, version, if_none_match):
    header = if_none_match.format(v=version)
    response = api.get(SEARCH, query_string=FOUND, headers={"If-None-Match": header})
    assert response.status_code == HTTPStatus.NOT_MODIFIED
    assert response.get_data() == b""
    assert_cacheable(response, version)


def test_304_for_the_detail(api, version):
    path = detail_path(api)
    response = api.get(path, headers={"If-None-Match": f'"{version}"'})
    assert response.status_code == HTTPStatus.NOT_MODIFIED
    assert_cacheable(response, version)


def test_304_does_not_run_the_search(api, version, monkeypatch):
    api.get(SEARCH, query_string=FOUND)  # a versão já foi lida neste worker
    with failing_search(monkeypatch, RuntimeError("a busca não podia rodar")):
        response = api.get(
            SEARCH, query_string={"cargo": "medico"}, headers={"If-None-Match": f'"{version}"'}
        )
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_old_etag_gets_the_full_response(api, version):
    response = api.get(SEARCH, query_string=FOUND, headers={"If-None-Match": '"versao-antiga"'})
    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["data"]
    assert_cacheable(response, version)


def test_invalid_input_is_400_even_with_matching_etag(api, version):
    response = api.get(SEARCH, query_string={"uf": "XX"}, headers={"If-None-Match": "*"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert_not_stored(response)


def test_304_counts_against_the_rate_limit(make_app, schema_url, version):
    limit = 2
    client = make_app(
        DATABASE_URL=schema_url, API_CACHE_TTL_S=TTL_S, RATE_LIMIT_REQUESTS=limit
    ).test_client()
    headers = {"If-None-Match": f'"{version}"'}
    for _ in range(limit):
        response = client.get(SEARCH, query_string=FOUND, headers=headers)
        assert response.status_code == HTTPStatus.NOT_MODIFIED
    response = client.get(SEARCH, query_string=FOUND, headers=headers)
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS


# --- Cache desligado (API_CACHE_TTL_S=0) ---


@pytest.fixture
def uncached(make_app, schema_url):
    return make_app(DATABASE_URL=schema_url, API_CACHE_TTL_S=0)


def test_disabled_cache_sends_no_store_and_no_etag(uncached):
    client = uncached.test_client()
    for query in (FOUND, {"nome": "FULANO DE TAL"}):
        assert_not_stored(client.get(SEARCH, query_string=query))
    assert_not_stored(client.get(f"{SEARCH}/999999"))


def test_disabled_cache_never_answers_304_nor_reads_the_version(uncached, version):
    client = uncached.test_client()
    response = client.get(SEARCH, query_string=FOUND, headers={"If-None-Match": f'"{version}"'})
    assert response.status_code == HTTPStatus.OK
    response = client.get(SEARCH, query_string=FOUND, headers={"If-None-Match": "*"})
    assert response.status_code == HTTPStatus.OK
    assert uncached.extensions[EXTENSION_KEY].version.peek() is None


# --- Configuração ---


@pytest.fixture
def env(monkeypatch):
    for var in CACHE_ENV:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_default_ttl(env):
    assert c.load_config()["API_CACHE_TTL_S"] == c.DEFAULT_API_CACHE_TTL_S


@pytest.mark.parametrize(
    ("raw", "expected"), [("300", 300), ("0", 0), ("", c.DEFAULT_API_CACHE_TTL_S)]
)
def test_ttl_from_environment(env, raw, expected):
    env.setenv("API_CACHE_TTL_S", raw)
    assert c.load_config()["API_CACHE_TTL_S"] == expected


@pytest.mark.parametrize("raw", ["abc", "-1", "1.5"])
def test_invalid_ttl_falls_back_to_default(env, raw):
    env.setenv("API_CACHE_TTL_S", raw)
    assert c.load_config()["API_CACHE_TTL_S"] == c.DEFAULT_API_CACHE_TTL_S
