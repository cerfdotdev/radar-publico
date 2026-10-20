"""Testes da validação dos parâmetros de busca (sem banco)."""

from http import HTTPStatus

import pytest
from werkzeug.datastructures import MultiDict

from app.errors import ApiError
from app.search_params import (
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    MAX_PAGE,
    MAX_PER_PAGE,
    MAX_TEXT_LENGTH,
    Situacao,
    normalize_text,
    parse_search_params,
)


def parse(**args):
    return parse_search_params(MultiDict(args))


def error_code(**args) -> str:
    with pytest.raises(ApiError) as caught:
        parse(**args)
    assert caught.value.status == HTTPStatus.BAD_REQUEST
    return caught.value.code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Maria da Silva", "MARIA DA SILVA"),
        ("  José   Carlos  ", "JOSE CARLOS"),
        ("conceição", "CONCEICAO"),
        ("D'ÁVILA", "D'AVILA"),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_defaults_and_normalization():
    params = parse(nome="maría da silva", cargo="médico", orgao="saúde", uf=" rj ")
    assert (params.nome, params.cargo, params.orgao, params.uf) == (
        "MARIA DA SILVA",
        "MEDICO",
        "SAUDE",
        "RJ",
    )
    assert params.situacao is Situacao.TODOS
    assert (params.page, params.per_page) == (DEFAULT_PAGE, DEFAULT_PER_PAGE)


def test_situacao_and_paging():
    params = parse(uf="DF", situacao="Ativo", page="3", per_page="50")
    assert (params.situacao, params.page, params.per_page) == (Situacao.ATIVO, 3, 50)


def test_cargo_accepts_real_name_characters():
    assert parse(cargo="artifice de copa, camara").cargo == "ARTIFICE DE COPA, CAMARA"
    assert parse(orgao="DEP.DE CENTRAL").orgao == "DEP.DE CENTRAL"


def test_filter_is_required():
    assert error_code(situacao="ativo") == "FILTRO_OBRIGATORIO"
    assert error_code() == "FILTRO_OBRIGATORIO"


def test_unknown_parameter():
    assert error_code(uf="DF", bogus="1") == "PARAMETRO_DESCONHECIDO"


def test_similarity_now_available():
    params = parse(similar="%MARIA%")
    assert params.similar == "%MARIA%"



@pytest.mark.parametrize(
    "value",
    ["", " ", "a", "a" * (MAX_TEXT_LENGTH + 1), "a\x00b", "%", "_", "%MARIA%", "x--y", "x;y"],
)
def test_invalid_text(value):
    assert error_code(nome=value) == "PARAMETRO_INVALIDO"
    assert error_code(cargo=value) == "PARAMETRO_INVALIDO"


def test_nome_rejects_digits_but_cargo_accepts():
    assert error_code(nome="ARQUITETO 1") == "PARAMETRO_INVALIDO"
    assert parse(cargo="arquiteto 1").cargo == "ARQUITETO 1"


@pytest.mark.parametrize("value", ["XX", "D", "DFF", "DF' --"])
def test_invalid_uf(value):
    assert error_code(uf=value) == "UF_INVALIDA"


def test_invalid_uf_message_does_not_echo_long_input():
    with pytest.raises(ApiError) as caught:
        parse(uf="X" * 1000)
    assert len(caught.value.message) < 100


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("page", "0"),
        ("page", "-5"),
        ("page", "abc"),
        ("page", "1;select 1"),
        ("page", "99999999999999999999"),
        ("page", str(MAX_PAGE + 1)),
        ("page", "²"),
        ("per_page", "0"),
        ("per_page", str(MAX_PER_PAGE + 1)),
        ("per_page", "1 OR 1=1"),
    ],
)
def test_invalid_numbers(name, value):
    assert error_code(uf="DF", **{name: value}) == "PARAMETRO_INVALIDO"


def test_invalid_situacao():
    assert error_code(uf="DF", situacao="foo") == "PARAMETRO_INVALIDO"
