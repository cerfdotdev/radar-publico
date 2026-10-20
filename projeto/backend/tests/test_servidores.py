"""Testes de GET /api/servidores e /api/servidores/<id> contra um Postgres real (o do CI).

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
from app.search_params import MAX_ID

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "init" / "01-schema.sql"

ORGAOS = [
    ("MINISTERIO DA SAUDE", "MS"),
    ("INSTITUTO NACIONAL DE SEGURO SOCIAL", "INSS"),
    ("COLEGIO PEDRO II", None),
    ("UNIVERSIDADE FEDERAL DO RIO GRANDE", "FURG"),
]
CARGOS = [
    "MEDICO",
    "PROFESSOR DO MAGISTERIO SUPERIOR",
    "PROFESSOR ENS BASICO TECN TECNOLOGICO",
    "AGENTE ADMINISTRATIVO",
    "TECNICO DE LABORATORIO",
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
    # Nomes que, digitados com '%' cru (%DE%BA, %DE%AB), formam UTF-8 válido.
    ("JOSE DE BARROS", "ativo", "TECNICO DE LABORATORIO",
     "UNIVERSIDADE FEDERAL DO RIO GRANDE", "RS", Decimal("8000.00")),
    ("MARIA DE ABREU", "aposentado", "TECNICO DE LABORATORIO",
     "UNIVERSIDADE FEDERAL DO RIO GRANDE", None, Decimal("5000.00")),
]  # fmt: skip
# Campos só do detalhe, nos dois vínculos de MARIA DA SILVA.
DETALHE_ATIVO = {"codigo_carreira": "301005", "data_ingresso": "2010-03-01"}
DETALHE_APOSENTADO = {
    "tipo_aposentadoria": "VOLUNTARIA",
    "fundamento_legal": "CF 40 III C",
    "portaria": "LEI 014600/2023, AUT.EXT.: PR PUB: DO 19JUN2023",
    "data_aposentadoria": "1990-07-02",
    "forma_ingresso": "ADMISSAO SEM CONCURSO PUBLICO",
    "data_ingresso": "1959-10-01",
    "referencia": "2026-05",
}
DETALHE_UPDATE = """
    UPDATE servidor SET {campos} WHERE nome = 'MARIA DA SILVA' AND situacao = %(situacao)s
"""


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
        for situacao, campos in (("ativo", DETALHE_ATIVO), ("aposentado", DETALHE_APOSENTADO)):
            assignments = sql.SQL(", ").join(
                sql.SQL("{} = {}").format(sql.Identifier(campo), sql.Placeholder(campo))
                for campo in campos
            )
            conn.execute(
                sql.SQL(DETALHE_UPDATE).format(campos=assignments),
                {**campos, "situacao": situacao},
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


# --- Busca por similaridade com filtros ---


def test_similar_orders_by_similarity(api):
    status, body = search(api, similar="%maria%silva%")
    assert status == HTTPStatus.OK
    assert names(body) == ["MARIA DA SILVA", "MARIA DA SILVA"]
    assert all(0 < item["similaridade"] <= 1 for item in body["data"])
    assert body["meta"] == {
        "total": 2,
        "total_exato": True,
        "page": 1,
        "per_page": 100,
        "total_pages": 1,
    }


def test_similar_limit(api):
    status, body = search(api, similar="%SILVA%", limit=1)
    assert status == HTTPStatus.OK
    assert len(body["data"]) == 1
    assert body["meta"]["per_page"] == 1


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({"cargo": "medico"}, [("MARIA DA SILVA", "ativo")]),
        ({"orgao": "inss"}, [("MARIA DA SILVA", "aposentado")]),
        ({"uf": "DF"}, [("MARIA DA SILVA", "ativo")]),
        ({"situacao": "aposentado"},
         [("MARIA DA SILVA", "aposentado"), ("MARIA DE ABREU", "aposentado")]),
        ({"situacao": "ativo", "orgao": "furg"}, None),
        ({"cargo": "tecnico", "orgao": "rio grande", "situacao": "aposentado"},
         [("MARIA DE ABREU", "aposentado")]),
    ],
)  # fmt: skip
def test_similar_combines_with_filters(api, query, expected):
    status, body = search(api, similar="%MARIA%", **query)
    if expected is None:
        assert status == HTTPStatus.NOT_FOUND
        assert body["error"]["code"] == "NAO_ENCONTRADO"
        return
    assert status == HTTPStatus.OK
    assert sorted((item["nome"], item["situacao"]) for item in body["data"]) == expected


def test_similar_with_uf_finds_only_that_uf(api):
    status, body = search(api, similar="%SILVA%", uf="rj")
    assert status == HTTPStatus.OK
    assert names(body) == ["JOSE CARLOS DA SILVA"]
    assert body["data"][0]["uf"] == "RJ"


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ({"cargo": "astronauta"}, "CARGO_NAO_ENCONTRADO"),
        ({"orgao": "nasa"}, "ORGAO_NAO_ENCONTRADO"),
        ({"uf": "DF", "situacao": "aposentado"}, "NAO_ENCONTRADO"),
        ({"uf": "AC"}, "NAO_ENCONTRADO"),
    ],
)
def test_similar_with_filters_not_found(api, query, code):
    status, body = search(api, similar="%MARIA%", **query)
    assert status == HTTPStatus.NOT_FOUND
    assert body["error"]["code"] == code


@pytest.mark.parametrize("paging", [{"page": 1}, {"per_page": 20}, {"page": 2, "per_page": 50}])
def test_similar_rejects_paging(api, paging):
    status, body = search(api, similar="%MARIA%", **paging)
    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"]["code"] == "PARAMETRO_INVALIDO"
    assert "'similar'" in body["error"]["message"]


# --- Aspas e '%' digitados como no enunciado ---


def raw_search(api, query_string: str):
    """Query string exatamente como digitada no curl ou no navegador, sem codificar."""
    response = api.get(f"/api/servidores?{query_string}")
    return response.status_code, response.get_json()


@pytest.mark.parametrize(
    ("query_string", "expected"),
    [
        ("similar=%JOSE%DE%BARROS%&limit=100", ["JOSE DE BARROS"]),
        ("similar=%MARIA%DE%ABREU%", ["MARIA DE ABREU"]),
        ("similar=%CARLOS%", ["JOSE CARLOS DA SILVA"]),
        ("similar=%MARIA%DA%SILVA%&limit=100", ["MARIA DA SILVA", "MARIA DA SILVA"]),
        ('similar="%MARIA%DA%SILVA%"&limit=100', ["MARIA DA SILVA", "MARIA DA SILVA"]),
        ("similar=%22%25MARIA%25DA%25SILVA%25%22", ["MARIA DA SILVA", "MARIA DA SILVA"]),
        ("similar=%E2%80%9D%MARIA%DA%SILVA%%E2%80%9D", ["MARIA DA SILVA", "MARIA DA SILVA"]),
        ("similar=%E2%80%9C%25JOSE%25SILVA%25%E2%80%9D", ["JOSE CARLOS DA SILVA"]),
        ('nome="Maria da Silva"&uf=DF', ["MARIA DA SILVA"]),
        ("nome=Jos%C3%A9+de+Barros", ["JOSE DE BARROS"]),
        ('cargo="professor"&orgao=“pedro”', ["ANA COSTA", "JOSE CARLOS DA SILVA"]),
    ],
)
def test_raw_query_strings_from_the_assignment(api, query_string, expected):
    status, body = raw_search(api, query_string)
    assert status == HTTPStatus.OK, body
    assert names(body) == expected


@pytest.mark.parametrize(
    "query_string",
    [
        "similar=%' OR 1=1 --",
        "similar=%MARIA%;DROP TABLE servidor",
        "similar=%MARIA%' UNION SELECT 1 --",
        "nome=x' OR '1'='1",
        "nome=%27%20OR%201%3D1",
        "cargo=a'/**/OR/**/1=1",
        "orgao=saude%00",
        'similar="%MARIA%',
        r"similar=%MARIA\%",
        "similar=%MA_IA%",
    ],
)
def test_injection_attempts_are_rejected(api, query_string):
    status, body = raw_search(api, query_string)
    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"]["code"] == "PARAMETRO_INVALIDO"


# --- GET /api/servidores/<id> ---


def id_of(api, nome: str, situacao: str) -> int:
    _, body = search(api, nome=nome, situacao=situacao)
    [item] = body["data"]
    return item["id"]


def detail(api, servidor_id, query: dict | None = None):
    response = api.get(f"/api/servidores/{servidor_id}", query_string=query)
    return response.status_code, response.get_json()


def test_detail_of_retired_servant(api):
    servidor_id = id_of(api, "MARIA DA SILVA", "aposentado")
    status, body = detail(api, servidor_id)
    assert status == HTTPStatus.OK
    assert body == {
        "data": {
            "id": servidor_id,
            "nome": "MARIA DA SILVA",
            "situacao": "aposentado",
            "cargo": "AGENTE ADMINISTRATIVO",
            "orgao": "INSTITUTO NACIONAL DE SEGURO SOCIAL",
            "sigla_orgao": "INSS",
            "uf": None,
            "valor": 6233.17,
            "codigo_carreira": None,
            **DETALHE_APOSENTADO,
        }
    }


def test_detail_of_active_servant(api):
    servidor_id = id_of(api, "MARIA DA SILVA", "ativo")
    status, body = detail(api, servidor_id)
    assert status == HTTPStatus.OK
    data = body["data"]
    assert (data["situacao"], data["uf"], data["valor"]) == ("ativo", "DF", 15000.5)
    assert data["codigo_carreira"] == "301005"
    assert data["data_ingresso"] == "2010-03-01"
    assert data["data_aposentadoria"] is None
    assert data["tipo_aposentadoria"] is None
    assert data["referencia"] == "2026-08"


def test_detail_with_null_cargo(api):
    status, body = detail(api, id_of(api, "JOAO PEREIRA", "aposentado"))
    assert status == HTTPStatus.OK
    assert body["data"]["cargo"] is None


@pytest.mark.parametrize("servidor_id", [MAX_ID, 999_999])
def test_detail_not_found(api, servidor_id):
    status, body = detail(api, servidor_id)
    assert status == HTTPStatus.NOT_FOUND
    assert body["error"]["code"] == "NAO_ENCONTRADO"


@pytest.mark.parametrize(
    "servidor_id",
    [
        "abc",
        "0",
        "-1",
        "1.5",
        "1e3",
        "%20",
        "1%20OR%201=1",
        "1;DROP%20TABLE%20servidor",
        str(MAX_ID + 1),
        "9" * 40,
        "%D9%A1%D9%A2",
        "²",
    ],
)
def test_detail_bad_id_never_reaches_the_database(api, servidor_id):
    status, body = detail(api, servidor_id)
    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"]["code"] == "PARAMETRO_INVALIDO"
    assert body["error"]["message"].startswith("'id'")


def test_detail_rejects_query_parameters(api):
    status, body = detail(api, 1, {"campos": "todos"})
    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"]["code"] == "PARAMETRO_DESCONHECIDO"


def test_detail_only_accepts_get(api):
    response = api.post("/api/servidores/1")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.get_json()["error"]["code"] == "METODO_NAO_PERMITIDO"
