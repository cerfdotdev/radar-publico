"""Validação local com as regras de app/search_params.py do backend."""

import pytest

from radar_desktop.api import Busca, Situacao
from radar_desktop.validacao import UFS, normalizar_texto, validar_busca

TEXTO_LONGO = "A" * 101


def campo_do_erro(busca: Busca) -> str | None:
    erro = validar_busca(busca)
    return erro.campo if erro is not None else None


@pytest.mark.parametrize(
    "busca",
    [
        Busca(nome="José D'Ávila"),
        Busca(nome="Maria da Silva", cargo="professor", orgao="INSS", uf="DF"),
        Busca(nome="Ana", situacao=Situacao.APOSENTADO),
        Busca(similar="%MARIA%SILVA%", limite=50),
        Busca(similar="JOSE%SILVA"),
        Busca(cargo="PROFESSOR DO MAGISTERIO SUPERIOR (CLASSE A), 2/3"),
        Busca(orgao="MS"),
        Busca(uf="RJ", situacao=Situacao.ATIVO),
        Busca(cargo="agente", pagina=10_000, por_pagina=1),
    ],
)
def test_buscas_validas(busca):
    assert validar_busca(busca) is None


@pytest.mark.parametrize(
    ("busca", "campo"),
    [
        (Busca(), "termo"),
        # 'situacao' sozinha não é filtro (FILTRO_OBRIGATORIO).
        (Busca(situacao=Situacao.ATIVO), "termo"),
        (Busca(nome="Maria", similar="MARIA"), "termo"),
        (Busca(nome="A"), "termo"),
        (Busca(nome=TEXTO_LONGO), "termo"),
        (Busca(nome="Maria 2"), "termo"),
        (Busca(nome="Maria%"), "termo"),
        (Busca(nome="Maria--Silva"), "termo"),
        (Busca(similar="%%%"), "termo"),
        (Busca(similar="MA%"), "termo"),
        (Busca(similar="%MARIA;DROP%"), "termo"),
        (Busca(similar="MARIA", limite=0), "limite"),
        (Busca(similar="MARIA", limite=101), "limite"),
        (Busca(cargo="A"), "cargo"),
        (Busca(cargo="professor;"), "cargo"),
        (Busca(orgao=TEXTO_LONGO), "orgao"),
        (Busca(orgao="saude--"), "orgao"),
        (Busca(uf="XX"), "uf"),
        (Busca(uf="DF", situacao=Situacao.APOSENTADO), "uf"),
        (Busca(cargo="agente", pagina=0), "pagina"),
        (Busca(cargo="agente", pagina=10_001), "pagina"),
        (Busca(cargo="agente", por_pagina=101), "por_pagina"),
    ],
)
def test_buscas_invalidas(busca, campo):
    assert campo_do_erro(busca) == campo


def test_tres_letras_contam_depois_da_normalizacao():
    assert validar_busca(Busca(similar="%Á%É%Í%")) is None


def test_limite_so_conta_com_similar():
    assert validar_busca(Busca(nome="Maria", limite=0)) is None


def test_normalizacao_igual_a_do_backend():
    assert normalizar_texto("  José   d'Ávila ") == "JOSE D'AVILA"


def test_27_ufs():
    assert len(UFS) == len(set(UFS)) == 27
