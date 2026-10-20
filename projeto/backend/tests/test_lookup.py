"""Cargos e órgãos na memória do worker (app/lookup.py) contra o SQL que a busca usava.

A resolução em memória tem de achar exatamente os mesmos ids que o LIKE '%texto%' com
escape de antes, inclusive com % _ e \\ no texto (a validação recusa esses caracteres em
cargo e órgão, mas a comparação não pode depender disso).
"""

import random
import threading
import time
from http import HTTPStatus

import psycopg
import pytest

from app.db import get_db_connection
from app.lazy import Lazy
from app.lookup import EXTENSION_KEY, Lookup, get_lookup
from tests.db_schema import temporary_schema

# O SQL que resolvia cargo e órgão a cada busca, antes do cache em memória.
LIKE_ESCAPE = "\\"
CARGO_SQL = "SELECT id FROM cargo WHERE nome LIKE %s"
ORGAO_SQL = "SELECT id FROM orgao WHERE nome LIKE %s OR sigla = %s"

CARGOS = [
    "MEDICO",
    "PROFESSOR DO MAGISTERIO SUPERIOR",
    "PROFESSOR ENS BASICO TECN TECNOLOGICO",
    "AGENTE_ADMINISTRATIVO",
    "AGENTE ADMINISTRATIVO",
    "GRATIFICACAO 50% DO VALOR",
    "GRATIFICACAO 50 DO VALOR",
    "TECNICO A\\B",
    "TECNICO AB",
    "100%_\\",
    "%",
    "_",
    "\\",
    "ANALISTA (TI) / SUPORTE, NIVEL 2",
]
# (nome, sigla): siglas ausentes, iguais a parte de outro nome e com caracteres do LIKE.
ORGAOS = [
    ("MINISTERIO DA SAUDE", "MS"),
    ("INSTITUTO NACIONAL DE SEGURO SOCIAL", "INSS"),
    ("COLEGIO PEDRO II", None),
    ("UNIVERSIDADE FEDERAL DO RIO GRANDE", "FURG"),
    ("FUNDACAO MS SAUDE", None),
    ("ORGAO A_B", "A_B"),
    ("ORGAO AXB", "AXB"),
    ("ORGAO 50%", "50%"),
    ("ORGAO 500", None),
    ("ORGAO C\\D", "C\\D"),
]
TERMS = [
    "%",
    "_",
    "\\",
    "%%",
    "%_",
    "_%",
    "50%",
    "0%_",
    "%_\\",
    "A_B",
    "A\\B",
    "C\\D",
    "\\B",
    "B\\",
    "MEDICO",
    "EDIC",
    "medico",
    "PROFESSOR",
    "PROFESSOR DO",
    "AGENTE_",
    "AGENTE ",
    "MS",
    "INSS",
    "M",
    "SAUDE",
    "FURG",
    "AXB",
    "(TI) /",
    ", NIVEL",
    "INEXISTENTE",
    "",
]
# Termos aleatórios: pedaços dos nomes e textos montados com os caracteres do LIKE.
RANDOM_SEED = 54
RANDOM_TERMS = 300
RANDOM_ALPHABET = "AB_%\\ 05"
MAX_RANDOM_LENGTH = 4
CONCURRENT_THREADS = 8
# Tempo para as outras threads chegarem ao lock enquanto a primeira carrega.
CONTENTION_WAIT_S = 0.1
LOAD_TIMEOUT_S = 5


def like_contains(text: str) -> str:
    """Padrão LIKE de "contém", com % _ e \\ da entrada tratados como texto."""
    escaped = (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


def populate(conn) -> None:
    conn.cursor().executemany("INSERT INTO cargo (nome) VALUES (%s)", [(c,) for c in CARGOS])
    conn.cursor().executemany("INSERT INTO orgao (nome, sigla) VALUES (%s, %s)", ORGAOS)


@pytest.fixture(scope="module")
def schema_url(database_url):
    with temporary_schema(database_url, populate) as url:
        yield url


@pytest.fixture
def app(make_app, schema_url):
    return make_app(DATABASE_URL=schema_url)


@pytest.fixture
def lookup(app) -> Lookup:
    with app.app_context():
        return get_lookup()


def sql_ids(app, query: str, args: tuple) -> list[int]:
    with app.app_context(), get_db_connection() as conn:
        return sorted(row[0] for row in conn.execute(query, args))


def random_terms() -> list[str]:
    rng = random.Random(RANDOM_SEED)
    names = CARGOS + [nome for nome, _ in ORGAOS]
    terms = []
    for _ in range(RANDOM_TERMS):
        if rng.random() < 0.5:
            name = rng.choice(names)
            start = rng.randrange(len(name))
            terms.append(name[start : start + rng.randint(1, MAX_RANDOM_LENGTH)])
        else:
            length = rng.randint(1, MAX_RANDOM_LENGTH)
            terms.append("".join(rng.choice(RANDOM_ALPHABET) for _ in range(length)))
    return terms


def test_like_wildcards_are_escaped():
    assert like_contains("50%_A\\B") == "%50\\%\\_A\\\\B%"


@pytest.mark.parametrize("term", TERMS)
def test_cargo_matches_the_sql_like(app, lookup, term):
    assert sorted(lookup.cargo_ids(term)) == sql_ids(app, CARGO_SQL, (like_contains(term),))


@pytest.mark.parametrize("term", TERMS)
def test_orgao_matches_the_sql_like_or_sigla(app, lookup, term):
    expected = sql_ids(app, ORGAO_SQL, (like_contains(term), term))
    assert sorted(lookup.orgao_ids(term)) == expected


def test_random_terms_match_the_sql(app, lookup):
    for term in random_terms():
        cargo_sql = sql_ids(app, CARGO_SQL, (like_contains(term),))
        orgao_sql = sql_ids(app, ORGAO_SQL, (like_contains(term), term))
        assert sorted(lookup.cargo_ids(term)) == cargo_sql, term
        assert sorted(lookup.orgao_ids(term)) == orgao_sql, term


def test_special_characters_are_literal(lookup):
    by_id = {cargo.id: cargo.nome for cargo in lookup.cargos}
    assert [by_id[i] for i in lookup.cargo_ids("_")] == ["AGENTE_ADMINISTRATIVO", "100%_\\", "_"]
    assert [by_id[i] for i in lookup.cargo_ids("50%")] == ["GRATIFICACAO 50% DO VALOR"]
    assert [by_id[i] for i in lookup.cargo_ids("A\\B")] == ["TECNICO A\\B"]


def test_sigla_is_exact_and_null_never_matches(lookup):
    by_id = {orgao.id: orgao.nome for orgao in lookup.orgaos}
    # 'MS' é a sigla do ministério e parte do nome da fundação (que não tem sigla).
    assert sorted(by_id[i] for i in lookup.orgao_ids("MS")) == [
        "FUNDACAO MS SAUDE",
        "MINISTERIO DA SAUDE",
    ]
    assert [by_id[i] for i in lookup.orgao_ids("FURG")] == ["UNIVERSIDADE FEDERAL DO RIO GRANDE"]


# --- Carga preguiçosa, uma vez por worker ---


def search(client, **query):
    response = client.get("/api/servidores", query_string=query)
    return response.status_code, response.get_json()


def test_tables_are_read_only_on_first_cargo_or_orgao_filter(app):
    lazy = app.extensions[EXTENSION_KEY]
    client = app.test_client()
    assert lazy.peek() is None
    search(client, nome="MARIA")
    assert lazy.peek() is None
    status, body = search(client, cargo="medico")
    # O schema do teste não tem servidores: cargo achado, nenhum vínculo.
    assert (status, body["error"]["code"]) == (HTTPStatus.NOT_FOUND, "NAO_ENCONTRADO")
    assert lazy.peek() is not None


def test_searches_use_memory_until_the_process_restarts(make_app, schema_url, app):
    client = app.test_client()
    assert search(client, cargo="medico")[0] == HTTPStatus.NOT_FOUND
    novo = "CARGO CRIADO DEPOIS DA CARGA"
    with psycopg.connect(schema_url, autocommit=True) as conn:
        conn.execute("INSERT INTO cargo (nome) VALUES (%s)", (novo,))
    try:
        # Sem consultar o banco, este worker não vê o cargo novo.
        status, body = search(client, cargo=novo)
        assert (status, body["error"]["code"]) == (HTTPStatus.NOT_FOUND, "CARGO_NAO_ENCONTRADO")
        # Um processo novo (worker reciclado ou backend reiniciado) lê as tabelas de novo.
        status, body = search(make_app(DATABASE_URL=schema_url).test_client(), cargo=novo)
        assert (status, body["error"]["code"]) == (HTTPStatus.NOT_FOUND, "NAO_ENCONTRADO")
    finally:
        with psycopg.connect(schema_url, autocommit=True) as conn:
            conn.execute("DELETE FROM cargo WHERE nome = %s", (novo,))


def test_lazy_loads_once_with_concurrent_threads():
    calls = []
    loading, release = threading.Event(), threading.Event()
    start = threading.Barrier(CONCURRENT_THREADS)

    def load():
        calls.append(threading.get_ident())
        loading.set()
        release.wait(timeout=LOAD_TIMEOUT_S)
        return object()

    lazy = Lazy(load)
    results = []

    def worker():
        start.wait()
        results.append(lazy.get())

    threads = [threading.Thread(target=worker) for _ in range(CONCURRENT_THREADS)]
    for thread in threads:
        thread.start()
    assert loading.wait(timeout=LOAD_TIMEOUT_S)
    # A primeira thread segura o lock; as outras chegam a ele e esperam.
    time.sleep(CONTENTION_WAIT_S)
    release.set()
    for thread in threads:
        thread.join()
    assert len(calls) == 1
    assert len(results) == CONCURRENT_THREADS
    assert all(result is results[0] for result in results)


def test_lazy_retries_after_a_failed_load():
    attempts = []

    def load():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("banco indisponível")
        return "carregado"

    lazy = Lazy(load)
    with pytest.raises(RuntimeError):
        lazy.get()
    assert lazy.peek() is None
    assert lazy.get() == "carregado"
    assert lazy.get() == "carregado"
    assert len(attempts) == 2
