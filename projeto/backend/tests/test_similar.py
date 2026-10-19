"""Testes mínimos da busca por similaridade (?similar= e limit)."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.datastructures import MultiDict

from app.errors import ApiError
from app.search_params import parse_search_params

# --- Validação de parâmetros (sem banco) ---


def parse(**args):
    return parse_search_params(MultiDict(args))


def error_code(**args) -> str:
    with pytest.raises(ApiError) as caught:
        parse(**args)
    return caught.value.code


def test_similar_valido():
    params = parse(similar="%MARIA%SILVA%")
    assert params.similar == "%MARIA%SILVA%"
    assert params.limit == 100


def test_similar_limit_customizado():
    params = parse(similar="JOSE%SILVA", limit="50")
    assert params.similar == "JOSE%SILVA"
    assert params.limit == 50


def test_similar_e_nome_juntos_retorna_erro():
    assert error_code(similar="%MARIA%", nome="JOSE SILVA") == "PARAMETRO_INVALIDO"


def test_limit_sem_similar_retorna_erro():
    assert error_code(nome="JOSE SILVA", limit="10") == "PARAMETRO_INVALIDO"


def test_similar_poucas_letras_retorna_erro():
    assert error_code(similar="MA%") == "PARAMETRO_INVALIDO"


def test_similar_caractere_proibido_retorna_erro():
    assert error_code(similar="%MARIA;DROP%") == "PARAMETRO_INVALIDO"


def test_limit_fora_da_faixa_retorna_erro():
    assert error_code(similar="%MARIA%", limit="0") == "PARAMETRO_INVALIDO"
    assert error_code(similar="%MARIA%", limit="101") == "PARAMETRO_INVALIDO"


# --- Rota /api/servidores com similar (mock de banco) ---


def _mock_row(nome, similaridade=0.75):
    return {
        "id": 1,
        "nome": nome,
        "situacao": "ativo",
        "cargo": "MEDICO",
        "orgao": "MINISTERIO DA SAUDE",
        "sigla_orgao": "MS",
        "uf": "DF",
        "valor": 15000.50,
        "similaridade": similaridade,
    }


def test_similar_retorna_200_com_similaridade(client):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = [_mock_row("MARIA SILVA", 0.82)]

    with patch("app.routes.servidores.get_db_connection") as mock_get:
        mock_get.return_value.__enter__.return_value = mock_conn
        response = client.get("/api/servidores", query_string={"similar": "%MARIA%SILVA%"})

    assert response.status_code == HTTPStatus.OK
    body = response.get_json()
    assert len(body["data"]) == 1
    assert "similaridade" in body["data"][0]
    assert body["meta"]["total"] == 1


def test_similar_sem_resultado_retorna_404(client):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = []

    with patch("app.routes.servidores.get_db_connection") as mock_get:
        mock_get.return_value.__enter__.return_value = mock_conn
        response = client.get("/api/servidores", query_string={"similar": "%FULANO%INEXISTENTE%"})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json()["error"]["code"] == "NAO_ENCONTRADO"
