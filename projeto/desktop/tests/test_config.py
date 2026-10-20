"""URL da API: variável de ambiente, padrão e validação."""

import pytest

from radar_desktop.config import API_URL_ENV, DEFAULT_API_URL, api_url_do_ambiente, validar_url


def test_padrao_e_a_base_do_contrato():
    assert DEFAULT_API_URL == "http://localhost:5000/api"
    assert api_url_do_ambiente({}) == DEFAULT_API_URL


def test_variavel_de_ambiente():
    assert api_url_do_ambiente({API_URL_ENV: " http://api:9000/api "}) == "http://api:9000/api"


def test_variavel_vazia_usa_o_padrao():
    assert api_url_do_ambiente({API_URL_ENV: "  "}) == DEFAULT_API_URL


@pytest.mark.parametrize(
    ("url", "esperada"),
    [
        ("http://localhost:5000/api/", "http://localhost:5000/api"),
        (" https://radar.exemplo.gov.br/api ", "https://radar.exemplo.gov.br/api"),
    ],
)
def test_url_valida(url, esperada):
    assert validar_url(url) == esperada


@pytest.mark.parametrize(
    "url",
    ["", "localhost:5000/api", "ftp://api/api", "file:///etc/passwd", "http://", "http://api:50O0"],
)
def test_url_invalida(url):
    with pytest.raises(ValueError, match="URL da API inválida"):
        validar_url(url)
