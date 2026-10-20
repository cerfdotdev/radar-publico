"""Formatação brasileira de valores, datas e textos ausentes."""

import math

import pytest

from radar_desktop.formatacao import (
    SEM_VALOR,
    formatar_data,
    formatar_inteiro,
    formatar_moeda,
    formatar_orgao,
    formatar_referencia,
    texto_intervalo,
    texto_ou_travessao,
    texto_total,
)


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (19090.67, "R$ 19.090,67"),
        (1234567.5, "R$ 1.234.567,50"),
        (0, "R$ 0,00"),
        (0.005, "R$ 0,01"),
        (None, SEM_VALOR),
        (math.nan, SEM_VALOR),
        (math.inf, SEM_VALOR),
        (True, SEM_VALOR),
    ],
)
def test_moeda(valor, texto):
    assert formatar_moeda(valor) == texto


def test_inteiro():
    assert formatar_inteiro(10_000) == "10.000"
    assert formatar_inteiro(7) == "7"


@pytest.mark.parametrize(("valor", "texto"), [(None, SEM_VALOR), ("", SEM_VALOR), ("DF", "DF")])
def test_texto_ausente_vira_travessao(valor, texto):
    assert texto_ou_travessao(valor) == texto


def test_datas():
    assert formatar_data("1990-07-02") == "02/07/1990"
    assert formatar_data(None) == SEM_VALOR
    assert formatar_data("02/07/1990") == "02/07/1990"
    assert formatar_referencia("2026-05") == "05/2026"
    assert formatar_referencia(None) == SEM_VALOR
    assert formatar_referencia("maio") == "maio"


def test_orgao_com_e_sem_sigla():
    assert formatar_orgao("MINISTERIO DA SAUDE", "MS") == "MINISTERIO DA SAUDE (MS)"
    assert formatar_orgao("CONTROLADORIA-GERAL DA UNIAO", None) == "CONTROLADORIA-GERAL DA UNIAO"


def test_total():
    assert texto_total(1, True) == "1 resultado encontrado"
    assert texto_total(1234, True) == "1.234 resultados encontrados"
    assert texto_total(10_000, False) == "Mais de 10.000 resultados"


def test_intervalo():
    assert texto_intervalo(2, 20, 20, 1234) == "Mostrando 21–40 de 1.234."
    assert texto_intervalo(1, 20, 5, 5) is None
