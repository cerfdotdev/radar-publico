"""Testes de GET /api/servidores contra um Postgres real (o banco vazio do CI).

O fixture cria um schema temporário com projeto/db/init/01-schema.sql e poucas linhas
conhecidas; a aplicação de teste usa esse schema pelo search_path.
"""

import os
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.routes import servidores
from app.routes.servidores import like_contains

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "init" / "01-schema.sql"

ORGAOS = [
    ("MINISTERIO DA SAUDE", "MS"),
    ("INSTITUTO NACIONAL DE SEGURO SOCIAL", "INSS"),
    ("COLEGIO PEDRO II", None),
]
CARGOS = [
    "MEDICO",
    "PROFESSOR DO MAGISTERIO SUPERIOR",
    "PROFESSOR ENS BASICO TECN TECNOLOGICO",
    "AGENTE ADMINISTRATIVO",
]
# (nome, situacao, cargo ou None, órgão, uf, valor)
SERVIDORES = [
    ("MARIA DA SILVA", "ativo", "MEDICO", "MINISTERIO DA SAUDE", "DF", Decimal("15000.50")),
    ("MARIA DA SILVA", "aposentado", "AGENTE ADMINISTRATIVO",
     "INSTITUTO NACIONAL DE SEGURO SOCIAL", None, Decimal("6233.17")),
    ("JOSE CARLOS DA SILVA", "ativo", "PROFESSOR DO MAGISTERIO SUPERIOR",
     "COLEGIO PEDRO II", "RJ", Decimal("12000.00")),
    ("ANA COSTA", "ativo", "PROFESSOR ENS BASICO TECN TECNOLOGICO",
     "COLEGIO PEDRO II", "RJ", Decimal("9000.00")),
    ("JOAO PEREIRA", "aposentado", None, "MINISTERIO DA SAUDE", None, Decimal("4000.00")),
    ("PAULO LIMA", "ativo", "MEDICO", "INSTITUTO NACIONAL DE SEGURO SOCIAL", "SP",
     Decimal("18740.03")),
]  # fmt: skip


@pytest.fixture(scope="module")
def schema_url(database_url):
    """Schema temporário com as tabelas reais e as linhas acima."""
    schema = f"api_teste_{os.getpid()}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.cursor().executemany("INSERT INTO orgao (nome, sigla) VALUES (%s, %s)", ORGAOS)
        conn.cursor().executemany("INSERT INTO cargo (nome) VALUES (%s)", [(c,) for c in CARGOS])
        conn.cursor().executemany(
            """
            INSERT INTO servidor (nome, situacao, cargo_id, orgao_id, uf, valor, referencia)
            SELECT %s, %s, (SELECT id FROM cargo WHERE nome = %s),
                   (SELECT id FROM orgao WHERE nome = %s), %s, %s, '2026-08'
            """,
            SERVIDORES,
        )
    try:
        yield make_conninfo(database_url, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def api(make_app, schema_url):
    return make_app(DATABASE_URL=schema_url).test_client()


def search(api, **query):
    response = api.get("/api/servidores", query_string=query)
    return response.status_code, response.get_json()


def names(body) -> list[str]:
    return [item["nome"] for item in body["data"]]


def test_exact_name_ignores_case_accents_and_spaces(api):
    status, body = search(api, nome="  María da   silva ")
    assert status == HTTPStatus.OK
    assert names(body) == ["MARIA DA SILVA", "MARIA DA SILVA"]
    ativo, aposentado = body["data"]
    assert ativo == {
        "id": ativo["id"],
        "nome": "MARIA DA SILVA",
        "situacao": "ativo",
        "cargo": "MEDICO",
        "orgao": "MINISTERIO DA SAUDE",
        "sigla_orgao": "MS",
        "uf": "DF",
        "valor": 15000.5,
    }
    assert aposentado["uf"] is None
    assert aposentado["sigla_orgao"] == "INSS"
    assert body["meta"] == {
        "total": 2,
        "total_exato": True,
        "page": 1,
        "per_page": 20,
        "total_pages": 1,
    }


def test_cargo_contains_with_accents(api):
    status, body = search(api, cargo="médico")
    assert status == HTTPStatus.OK
    assert names(body) == ["MARIA DA SILVA", "PAULO LIMA"]


def test_cargo_matching_several_ids(api):
    status, body = search(api, cargo="professor")
    assert status == HTTPStatus.OK
    assert names(body) == ["ANA COSTA", "JOSE CARLOS DA SILVA"]


@pytest.mark.parametrize("orgao", ["inss", "seguro social"])
def test_orgao_by_sigla_or_name(api, orgao):
    status, body = search(api, orgao=orgao)
    assert status == HTTPStatus.OK
    assert names(body) == ["MARIA DA SILVA", "PAULO LIMA"]


def test_combined_filters(api):
    status, body = search(api, cargo="professor", orgao="pedro", uf="rj")
    assert status == HTTPStatus.OK
    assert names(body) == ["ANA COSTA", "JOSE CARLOS DA SILVA"]


def test_situacao_filter_and_null_cargo(api):
    status, body = search(api, orgao="saude", situacao="aposentado")
    assert status == HTTPStatus.OK
    assert names(body) == ["JOAO PEREIRA"]
    assert body["data"][0]["cargo"] is None


def test_uf_with_aposentado_is_never_found(api):
    status, body = search(api, uf="DF", situacao="aposentado")
    assert status == HTTPStatus.NOT_FOUND
    assert body["error"]["code"] == "NAO_ENCONTRADO"


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ({"cargo": "astronauta"}, "CARGO_NAO_ENCONTRADO"),
        ({"orgao": "nasa"}, "ORGAO_NAO_ENCONTRADO"),
        ({"nome": "fulano de tal"}, "NAO_ENCONTRADO"),
        ({"nome": "O'BRIEN"}, "NAO_ENCONTRADO"),
    ],
)
def test_not_found(api, query, code):
    status, body = search(api, **query)
    assert status == HTTPStatus.NOT_FOUND
    assert body["error"]["code"] == code


def test_pagination(api):
    status, body = search(api, uf="RJ", per_page=1, page=2)
    assert status == HTTPStatus.OK
    assert names(body) == ["JOSE CARLOS DA SILVA"]
    assert body["meta"]["total_pages"] == 2


def test_page_past_the_end(api):
    status, body = search(api, uf="RJ", per_page=1, page=3)
    assert status == HTTPStatus.NOT_FOUND
    assert body["error"]["code"] == "PAGINA_INEXISTENTE"


def test_total_is_capped(api, monkeypatch):
    cap = 1
    monkeypatch.setattr(servidores, "MAX_TOTAL", cap)
    monkeypatch.setattr(servidores, "COUNT_LIMIT", cap + 1)
    status, body = search(api, cargo="professor")
    assert status == HTTPStatus.OK
    assert len(body["data"]) == cap
    assert body["meta"]["total"] == cap
    assert body["meta"]["total_exato"] is False
    status, body = search(api, cargo="professor", per_page=1, page=2)
    assert status == HTTPStatus.NOT_FOUND


def test_invalid_input_never_reaches_the_database(api):
    status, body = search(api, nome="a\x00b", uf="DF")
    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"]["code"] == "PARAMETRO_INVALIDO"


def test_like_wildcards_are_escaped():
    assert like_contains("50%_A\\B") == "%50\\%\\_A\\\\B%"
