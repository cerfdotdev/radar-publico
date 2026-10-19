"""Testes da rota GET /api/servidores."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch


def test_filtro_obrigatorio_retorna_400(client):
    """Verifica erro 400 quando nenhum filtro é informado."""
    response = client.get("/api/servidores")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.is_json
    body = response.get_json()
    assert body["error"]["code"] == "FILTRO_OBRIGATORIO"


def test_uf_invalida_retorna_400(client):
    """Verifica erro 400 para UF inválida."""
    response = client.get("/api/servidores?uf=ZZ")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.is_json
    body = response.get_json()
    assert body["error"]["code"] == "UF_INVALIDA"


def test_cargo_nao_encontrado_retorna_404(client):
    """Verifica 404 quando o cargo não existe na tabela de cargos."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = []

    with patch("app.routes.servidores.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        response = client.get("/api/servidores?cargo=Inexistente")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json()["error"]["code"] == "CARGO_NAO_ENCONTRADO"


def test_orgao_nao_encontrado_retorna_404(client):
    """Verifica 404 quando o órgão não existe na tabela de órgãos."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = []

    with patch("app.routes.servidores.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        response = client.get("/api/servidores?orgao=Inexistente")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json()["error"]["code"] == "ORGAO_NAO_ENCONTRADO"


def test_busca_sucesso_retorna_200_json(client):
    """Verifica listagem de servidores com filtros combinados."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Simula resolução de cargo_ids, count e linhas de servidores
    mock_cur.fetchall.side_effect = [
        [(10,)],  # cargo_ids
        [(1, "MARIA DA SILVA", "ativo", "ANALISTA", "CGU", None, "DF", 15000.50)],  # rows
    ]
    mock_cur.fetchone.return_value = (1,)  # total_raw

    with patch("app.routes.servidores.get_db_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        response = client.get("/api/servidores?nome=Maria da Silva&cargo=analista&uf=DF")

    assert response.status_code == HTTPStatus.OK
    assert response.is_json
    body = response.get_json()

    assert "data" in body
    assert "meta" in body
    assert len(body["data"]) == 1

    item = body["data"][0]
    assert item["nome"] == "MARIA DA SILVA"
    assert item["cargo"] == "ANALISTA"
    assert item["uf"] == "DF"
    assert item["valor"] == 15000.50

    meta = body["meta"]
    assert meta["total"] == 1
    assert meta["total_exato"] is True
    assert meta["page"] == 1
