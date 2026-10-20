"""Testes da leitura da query string com '%' digitado sem codificar (app/query_string.py)."""

from http import HTTPStatus

import pytest

from app.query_string import parse_query_string

# Sem filtro válido, a busca responde antes de consultar o banco: estes testes não usam Postgres.
SEARCH_PATH = "/api/servidores"


def value_of(query_string: bytes) -> str:
    [(_, value)] = parse_query_string(query_string)
    return value


@pytest.mark.parametrize(
    "pattern",
    [
        # Duas letras de A a F depois do '%' formam um byte inválido sozinho: sempre funcionou.
        "%CARLOS%",
        "%DANIEL%",
        "%FABIO%",
        "%MARIA%DA%SILVA%",
        # %DE%BA, %DE%AB e %DA%BE formam UTF-8 válido (U+07BA, U+07AB, U+06BE): o Werkzeug
        # entregava esses caracteres e a busca respondia 400.
        "%JOSE%DE%BARROS%",
        "%MARIA%DE%ABREU%",
        "%ANA%DA%BEATRIZ%",
        "%CA%BENTO%",
        # 3 bytes que formariam U+ABBA, letra cherokee.
        "%EA%AE%BA%",
    ],
)
def test_percent_typed_raw_stays_as_typed(pattern):
    assert value_of(f"similar={pattern}".encode()) == pattern


@pytest.mark.parametrize(
    ("query_string", "expected"),
    [
        (b"similar=%25JOSE%25SILVA%25", "%JOSE%SILVA%"),
        (b"nome=Jos%C3%A9+da+Silva", "José da Silva"),
        (b"nome=jos%c3%a9", "josé"),
        (b"nome=Maria%20da%20Silva", "Maria da Silva"),
        (b"similar=%E2%80%9D%25MARIA%25%E2%80%9D", "”%MARIA%”"),
        (b"similar=%22%25MARIA%25%22", '"%MARIA%"'),
        (b"orgao=a%2Bb%26c%3Dd", "a+b&c=d"),
        (b"nome=Jos\xc3\xa9", "José"),
        # NUL e U+FFFD chegam à validação, que recusa com 400.
        (b"nome=a%00b", "a\x00b"),
        (b"nome=Maria\xff", "Maria�"),
        # Escape incompleto ou caractere que não serve à API ficam como texto.
        (b"similar=%MARIA%E", "%MARIA%E"),
        (b"similar=100%", "100%"),
        (b"nome=%C3%97", "%C3%97"),
    ],
)
def test_decodes_what_clients_encode(query_string, expected):
    assert value_of(query_string) == expected


def test_pairs_keep_order_and_blank_values():
    assert parse_query_string(b"nome=&uf&&cargo=a=b") == [
        ("nome", ""),
        ("uf", ""),
        ("cargo", "a=b"),
    ]
    assert parse_query_string(b"") == []


def test_raw_percent_reaches_the_search(client):
    response = client.get(f"{SEARCH_PATH}?similar=%JOSE%DE%BARROS%&limit=0")
    # O padrão passou na validação; quem recusa é o limit.
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"]["message"].startswith("'limit'")


def test_invalid_utf8_byte_is_400_not_500(client):
    response = client.get(SEARCH_PATH, environ_overrides={"QUERY_STRING": "similar=%MARIA\xff%"})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"]["code"] == "PARAMETRO_INVALIDO"


def test_invalid_utf8_byte_in_detail_id_is_400_not_500(client):
    # O id vem do caminho, que o Werkzeug decodifica com U+FFFD no lugar do byte inválido.
    response = client.get(
        f"{SEARCH_PATH}/1", environ_overrides={"PATH_INFO": f"{SEARCH_PATH}/1\xff"}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json()["error"]["message"].startswith("'id'")
