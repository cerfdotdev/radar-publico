"""Validações dos filtros, com as mesmas regras do frontend web (docs/api.md)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .api import Busca, LIMITE_MAX, LIMITE_MIN

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)
NOME_MIN_CHARS = 2
NOME_MAX_CHARS = 100
PER_PAGINA_MAX = 100

_NOME_PERMITIDO = re.compile(r"^[A-Z .'-]+$")
_SIMILAR_PERMITIDO = re.compile(r"^[A-Z .'%-]+$")
_TEXTO_PERMITIDO = re.compile(r"^[A-Z0-9 /(),.'-]+$")


@dataclass(frozen=True)
class ErroBusca:
    campo: str
    mensagem: str


def limpar_termo(valor: str) -> str:
    return " ".join(valor.split())


def normalizar_nome(valor: str) -> str:
    sem_acento = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caractere)
    )
    return limpar_termo(sem_acento).upper()


def _validar_texto(valor: str, rotulo: str) -> str | None:
    normalizado = normalizar_nome(valor)
    if normalizado == "":
        return None
    if len(normalizado) < NOME_MIN_CHARS:
        return f"O {rotulo} deve ter pelo menos {NOME_MIN_CHARS} caracteres."
    if len(normalizado) > NOME_MAX_CHARS:
        return f"O {rotulo} deve ter no máximo {NOME_MAX_CHARS} caracteres."
    if not _TEXTO_PERMITIDO.fullmatch(normalizado):
        return f"Use apenas letras, números e pontuação simples no {rotulo}."
    if "--" in normalizado:
        return "Não use dois hífens seguidos (--)."
    return None


def validar_busca(busca: Busca) -> ErroBusca | None:
    termo = busca.nome or busca.similar
    if termo == "" and busca.cargo == "" and busca.orgao == "" and busca.uf == "":
        return ErroBusca("termo", "Informe um nome ou ao menos um filtro para pesquisar.")

    if busca.nome and busca.similar:
        return ErroBusca("termo", "Use nome exato ou nome parecido, não os dois.")

    if termo != "":
        normalizado = normalizar_nome(termo)
        if len(normalizado) < NOME_MIN_CHARS:
            return ErroBusca("termo", f"O nome deve ter pelo menos {NOME_MIN_CHARS} caracteres.")
        if len(normalizado) > NOME_MAX_CHARS:
            return ErroBusca("termo", f"O nome deve ter no máximo {NOME_MAX_CHARS} caracteres.")
        permitido = _SIMILAR_PERMITIDO if busca.similar else _NOME_PERMITIDO
        if not permitido.fullmatch(normalizado):
            return ErroBusca("termo", "Use apenas letras e pontuação simples no nome.")
        if "--" in normalizado:
            return ErroBusca("termo", "Não use dois hífens seguidos (--).")
        if busca.similar and len(re.findall(r"[A-Z]", normalizado)) < 3:
            return ErroBusca("termo", "Use pelo menos 3 letras fora dos %.")

    if busca.similar and not LIMITE_MIN <= busca.limite <= LIMITE_MAX:
        return ErroBusca("limite", f"O limite deve estar entre {LIMITE_MIN} e {LIMITE_MAX}.")

    for rotulo, valor, campo in (
        ("cargo", busca.cargo, "cargo"),
        ("órgão", busca.orgao, "orgao"),
    ):
        mensagem = _validar_texto(valor, rotulo)
        if mensagem is not None:
            return ErroBusca(campo, mensagem)

    if busca.uf != "" and busca.uf not in UFS:
        return ErroBusca("uf", "Escolha uma UF válida.")
    if busca.pagina < 1:
        return ErroBusca("pagina", "A página deve ser maior que zero.")
    if not 1 <= busca.por_pagina <= PER_PAGINA_MAX:
        return ErroBusca("por_pagina", "Escolha de 1 a 100 resultados por página.")
    return None
