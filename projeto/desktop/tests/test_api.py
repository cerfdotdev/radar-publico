from __future__ import annotations

import io
import json
import socket
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from radar_desktop.api import (
    ApiError,
    Busca,
    RadarApiClient,
    buscar_servidores,
    montar_parametros,
)
from radar_desktop.config import DEFAULT_API_URL, api_url_from_env


def resposta_json(dados: object) -> MagicMock:
    resposta = MagicMock()
    resposta.__enter__.return_value = resposta
    resposta.read.return_value = json.dumps(dados).encode("utf-8")
    return resposta


class ConfiguracaoTests(unittest.TestCase):
    def test_url_padrao(self) -> None:
        self.assertEqual(api_url_from_env({}), DEFAULT_API_URL)

    def test_url_do_ambiente(self) -> None:
        self.assertEqual(api_url_from_env({"RADAR_API_URL": " http://api:9000 "}), "http://api:9000")

    def test_alias_do_ambiente(self) -> None:
        self.assertEqual(api_url_from_env({"API_URL": "http://api:9000/api"}), "http://api:9000/api")


class ParametrosTests(unittest.TestCase):
    def test_nome_exato_com_filtros(self) -> None:
        busca = Busca(nome="Maria da Silva", cargo="professor", orgao="INSS", uf="DF")
        self.assertEqual(
            busca.parametros(),
            [
                ("nome", "Maria da Silva"),
                ("cargo", "professor"),
                ("orgao", "INSS"),
                ("uf", "DF"),
            ],
        )

    def test_nome_parecido_envia_limite(self) -> None:
        busca = Busca(similar="%MARIA%SILVA%", limite=50)
        self.assertEqual(busca.parametros(), [("similar", "%MARIA%SILVA%"), ("limit", "50")])

    def test_paginacao_so_entra_quando_diferente_do_padrao(self) -> None:
        self.assertEqual(Busca(nome="Maria").parametros(), [("nome", "Maria")])
        self.assertEqual(
            Busca(nome="Maria", pagina=2, por_pagina=50).parametros(),
            [("nome", "Maria"), ("page", "2"), ("per_page", "50")],
        )

    def test_aliases_em_ingles(self) -> None:
        self.assertEqual(
            montar_parametros(nome="Maria", page=2, per_page=50),
            [("nome", "Maria"), ("page", "2"), ("per_page", "50")],
        )

    def test_similar_nao_pagina(self) -> None:
        self.assertEqual(
            Busca(similar="MARIA", limite=10, pagina=2, por_pagina=50).parametros(),
            [("similar", "MARIA"), ("limit", "10")],
        )

    def test_nome_e_similar_sao_exclusivos(self) -> None:
        with self.assertRaises(ValueError):
            Busca(nome="Maria", similar="MARIA").parametros()


class ClienteTests(unittest.TestCase):
    @patch("radar_desktop.api.urlopen")
    def test_busca_monta_url_e_devolve_json(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.return_value = resposta_json({"data": [], "meta": {"total": 0}})
        cliente = RadarApiClient("http://localhost:5000/")
        dados = cliente.buscar(nome="Maria", cargo="professor", uf="DF", page=2, per_page=50)

        self.assertEqual(dados["meta"]["total"], 0)
        requisicao = urlopen_mock.call_args.args[0]
        self.assertEqual(
            requisicao.full_url,
            "http://localhost:5000/api/servidores?nome=Maria&cargo=professor&uf=DF&page=2&per_page=50",
        )
        self.assertEqual(requisicao.get_header("Accept"), "application/json")

    @patch("radar_desktop.api.urlopen")
    def test_url_com_sufixo_api_nao_duplica(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.return_value = resposta_json({"data": [], "meta": {}})
        RadarApiClient("http://localhost:8080/api").buscar(similar="MARIA", limit=20)
        self.assertEqual(
            urlopen_mock.call_args.args[0].full_url,
            "http://localhost:8080/api/servidores?similar=MARIA&limit=20",
        )

    @patch("radar_desktop.api.urlopen")
    def test_detalhe(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.return_value = resposta_json({"data": {"id": 10, "nome": "MARIA"}})
        self.assertEqual(RadarApiClient("http://api").detalhar(10)["nome"], "MARIA")
        self.assertEqual(urlopen_mock.call_args.args[0].full_url, "http://api/api/servidores/10")

    @patch("radar_desktop.api.urlopen")
    def test_erro_http_usa_mensagem_da_api(self, urlopen_mock: MagicMock) -> None:
        corpo = json.dumps({"error": {"code": "NAO_ENCONTRADO", "message": "Nenhum servidor."}}).encode()
        urlopen_mock.side_effect = HTTPError(
            "http://api/api/servidores", 404, "Not Found", {}, io.BytesIO(corpo)
        )

        with self.assertRaises(ApiError) as contexto:
            RadarApiClient("http://api").buscar(nome="Maria")

        self.assertEqual(contexto.exception.codigo, "NAO_ENCONTRADO")
        self.assertEqual(contexto.exception.status, 404)
        self.assertEqual(contexto.exception.mensagem, "Nenhum servidor.")

    @patch("radar_desktop.api.urlopen")
    def test_429_informa_retry_after(self, urlopen_mock: MagicMock) -> None:
        corpo = json.dumps(
            {"error": {"code": "MUITAS_REQUISICOES", "message": "Muitas requisições."}}
        ).encode()
        urlopen_mock.side_effect = HTTPError(
            "http://api/api/servidores", 429, "Too Many Requests", {"Retry-After": "7"}, io.BytesIO(corpo)
        )

        with self.assertRaises(ApiError) as contexto:
            RadarApiClient("http://api").buscar(nome="Maria")

        self.assertEqual(contexto.exception.retry_after, 7)
        self.assertIn("7 s", contexto.exception.mensagem)

    @patch("radar_desktop.api.urlopen")
    def test_timeout(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.side_effect = URLError(socket.timeout())
        with self.assertRaises(ApiError) as contexto:
            RadarApiClient("http://api").buscar(nome="Maria")
        self.assertIn("demorou demais", contexto.exception.mensagem)

    @patch("radar_desktop.api.urlopen")
    def test_resposta_fora_do_contrato(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.return_value = resposta_json({"data": "não é lista", "meta": {}})
        with self.assertRaises(ApiError):
            RadarApiClient("http://api").buscar(nome="Maria")

    @patch("radar_desktop.api.urlopen")
    def test_atalho_buscar_servidores(self, urlopen_mock: MagicMock) -> None:
        urlopen_mock.return_value = resposta_json({"data": [], "meta": {"total": 0}})
        dados = buscar_servidores("http://api", nome="Maria")
        self.assertEqual(dados["data"], [])


if __name__ == "__main__":
    unittest.main()
