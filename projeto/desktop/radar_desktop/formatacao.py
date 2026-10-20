"""Textos e números no formato brasileiro, sem depender do Qt (docs/DESIGN.md)."""

import math

from .api import TOTAL_MAXIMO, Situacao

# Travessão para campo ausente na fonte, como no frontend web.
SEM_VALOR = "—"
CASAS_DECIMAIS = 2
# Troca os separadores do formato inglês (1,234.56) pelos do brasileiro (1.234,56).
_SEPARADORES_PT_BR = str.maketrans(",.", ".,")

ROTULOS_SITUACAO = {Situacao.ATIVO: "Ativo", Situacao.APOSENTADO: "Aposentado"}


def formatar_moeda(valor: float | None) -> str:
    """19090.67 -> 'R$ 19.090,67'. Valor ausente ou não finito vira travessão."""
    if valor is None or isinstance(valor, bool) or not math.isfinite(valor):
        return SEM_VALOR
    return f"R$ {valor:,.{CASAS_DECIMAIS}f}".translate(_SEPARADORES_PT_BR)


def formatar_inteiro(valor: int) -> str:
    """10000 -> '10.000'."""
    return f"{valor:,}".translate(_SEPARADORES_PT_BR)


def texto_ou_travessao(valor: str | None) -> str:
    return valor if valor else SEM_VALOR


def formatar_data(valor: str | None) -> str:
    """'1990-07-02' -> '02/07/1990'. Fora do formato ISO, devolve como veio."""
    if not valor:
        return SEM_VALOR
    partes = valor.split("-")
    if len(partes) != 3 or not all(parte.isdigit() for parte in partes):
        return valor
    ano, mes, dia = partes
    return f"{dia}/{mes}/{ano}"


def formatar_referencia(valor: str | None) -> str:
    """'2026-05' -> '05/2026'. Fora do formato, devolve como veio."""
    if not valor:
        return SEM_VALOR
    partes = valor.split("-")
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        return valor
    ano, mes = partes
    return f"{mes}/{ano}"


def formatar_orgao(orgao: str, sigla: str | None) -> str:
    """'MINISTERIO DA SAUDE' e 'MS' -> 'MINISTERIO DA SAUDE (MS)'."""
    return f"{orgao} ({sigla})" if sigla else orgao


def texto_total(total: int, total_exato: bool) -> str:
    """Título da lista: '1 resultado encontrado', '1.234 resultados…' ou 'Mais de 10.000…'."""
    if not total_exato:
        return f"Mais de {formatar_inteiro(TOTAL_MAXIMO)} resultados"
    rotulo = "resultado encontrado" if total == 1 else "resultados encontrados"
    return f"{formatar_inteiro(total)} {rotulo}"


def texto_intervalo(pagina: int, por_pagina: int, quantidade: int, total: int) -> str | None:
    """'Mostrando 21–40 de 1.234.' quando a página não traz todos os resultados."""
    if total <= quantidade:
        return None
    inicio = (pagina - 1) * por_pagina + 1
    fim = inicio + quantidade - 1
    return (
        f"Mostrando {formatar_inteiro(inicio)}–{formatar_inteiro(fim)} "
        f"de {formatar_inteiro(total)}."
    )
