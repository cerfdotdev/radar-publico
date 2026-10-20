"""--verificar: abre a janela fora da tela, consulta /health e não muda a execução normal.

Pulados se o Qt não puder ser carregado (ex.: sem as bibliotecas gráficas do sistema).
"""

import io
import os
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from radar_desktop import cli  # noqa: E402
from radar_desktop.verificacao import (  # noqa: E402
    CODIGO_FALHA,
    CODIGO_SUCESSO,
    PLATAFORMA_SEM_TELA,
    TEMPO_LIMITE_SAUDE_S,
    VARIAVEL_PLATAFORMA,
    consultar_saude,
    verificar,
)

API_URL = "http://api.teste/api"
SAUDE_OK = b'{"status": "ok"}'
URLOPEN = "radar_desktop.verificacao.urlopen"
SEM_CONEXAO = URLError(ConnectionRefusedError("Connection refused"))


def resposta(corpo: bytes) -> MagicMock:
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.read.return_value = corpo
    return mock


def test_saude_ok_consulta_o_health_da_base():
    with patch(URLOPEN, return_value=resposta(SAUDE_OK)) as urlopen:
        assert consultar_saude(API_URL) is None
    assert urlopen.call_args.args[0].full_url == f"{API_URL}/health"
    assert urlopen.call_args.kwargs["timeout"] == TEMPO_LIMITE_SAUDE_S


@pytest.mark.parametrize(
    ("falha", "motivo"),
    [
        (SEM_CONEXAO, "sem conexão: Connection refused"),
        (TimeoutError("timed out"), "sem conexão: timed out"),
        (HTTPError(f"{API_URL}/health", 503, "erro", {}, io.BytesIO()), "respondeu HTTP 503"),
    ],
)
def test_saude_indisponivel(falha, motivo):
    with patch(URLOPEN, side_effect=falha):
        assert consultar_saude(API_URL) == motivo


@pytest.mark.parametrize(
    ("corpo", "motivo"),
    [
        (b"<html></html>", "a resposta não é JSON"),
        (b'{"status": "erro"}', "resposta fora do formato de docs/api.md"),
        (b'["ok"]', "resposta fora do formato de docs/api.md"),
    ],
)
def test_saude_fora_do_contrato(corpo, motivo):
    with patch(URLOPEN, return_value=resposta(corpo)):
        assert consultar_saude(API_URL) == motivo


def test_verificar_abre_a_janela_e_informa_a_api(capsys):
    with patch(URLOPEN, return_value=resposta(SAUDE_OK)):
        assert cli.main(["--verificar", "--api-url", f"{API_URL}/"]) == CODIGO_SUCESSO
    saida = capsys.readouterr().out
    assert "janela ok" in saida
    assert f"API em {API_URL}: ok." in saida


def test_verificar_com_a_api_fora_do_ar_nao_falha(capsys):
    with patch(URLOPEN, side_effect=SEM_CONEXAO):
        assert cli.main(["--verificar", "--api-url", API_URL]) == CODIGO_SUCESSO
    assert f"API em {API_URL}: indisponível (sem conexão" in capsys.readouterr().out


def test_verificar_falha_se_a_janela_nao_abre(monkeypatch, capsys):
    def quebrar(*_args):
        raise RuntimeError("plugin ausente")

    monkeypatch.setattr("radar_desktop.verificacao.MainWindow", quebrar)
    with patch(URLOPEN) as urlopen:
        assert verificar(API_URL) == CODIGO_FALHA
    assert "falha ao abrir a janela: plugin ausente" in capsys.readouterr().err
    urlopen.assert_not_called()


def test_verificar_usa_offscreen_so_sem_plataforma_escolhida(monkeypatch):
    with patch(URLOPEN, return_value=resposta(SAUDE_OK)):
        monkeypatch.delenv(VARIAVEL_PLATAFORMA)
        verificar(API_URL)
        assert os.environ[VARIAVEL_PLATAFORMA] == PLATAFORMA_SEM_TELA

        monkeypatch.setenv(VARIAVEL_PLATAFORMA, "minimal")
        verificar(API_URL)
        assert os.environ[VARIAVEL_PLATAFORMA] == "minimal"


def test_sem_verificar_abre_o_app_normal(monkeypatch):
    abertos = []
    monkeypatch.setattr(cli, "run", lambda url: abertos.append(url) or CODIGO_SUCESSO)
    monkeypatch.setattr(cli, "verificar", lambda url: pytest.fail("não deveria verificar"))
    assert cli.main(["--api-url", f"{API_URL}/"]) == CODIGO_SUCESSO
    assert abertos == [API_URL]
