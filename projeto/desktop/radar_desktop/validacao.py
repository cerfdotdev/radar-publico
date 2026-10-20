"""Validação da busca com as regras do backend (app/search_params.py), antes de chamar a API.

Os textos são conferidos depois da mesma normalização da API: maiúsculas, sem acento
e com espaços simples.
"""

import math
import re
import unicodedata
from dataclasses import dataclass

from .api import LIMITE_MAX, LIMITE_MIN, TOTAL_MAXIMO, Busca, Situacao

TEXTO_MIN_CHARS = 2
TEXTO_MAX_CHARS = 100
# Um trecho entre os % com 3 letras seguidas: sem isso o índice trigram não filtra e a API
# lê a tabela inteira (MIN_TRIGRAM_LETTERS do backend).
SIMILAR_MIN_LETRAS_SEGUIDAS = 3
PAGINA_MIN = 1
POR_PAGINA_MIN = 1
POR_PAGINA_MAX = 100
# Só existem as páginas até o resultado de número TOTAL_MAXIMO.
PAGINA_MAX = math.ceil(TOTAL_MAXIMO / POR_PAGINA_MIN)

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)  # fmt: skip

NOME_PERMITIDO = re.compile(r"[A-Z .'-]+")
SIMILAR_PERMITIDO = re.compile(r"[A-Z .'%-]+")
CARGO_ORGAO_PERMITIDO = re.compile(r"[A-Z0-9 .'/(),-]+")
SEQUENCIA_PROIBIDA = "--"
# O espaço separa as letras (JO SE não serve), e o % nunca está no meio de uma sequência.
LETRAS_SEGUIDAS = re.compile(rf"[A-Z]{{{SIMILAR_MIN_LETRAS_SEGUIDAS},}}")
MENSAGEM_LETRAS_SEGUIDAS = (
    f"Use pelo menos um trecho com {SIMILAR_MIN_LETRAS_SEGUIDAS} letras seguidas entre os %."
)

CARACTERES_NOME = "letras, espaços, apóstrofo ('), ponto (.) e hífen (-)"
CARACTERES_SIMILAR = "letras, espaços, apóstrofo ('), ponto (.), hífen (-) e o curinga (%)"
CARACTERES_CARGO_ORGAO = (
    "letras, números, espaços, apóstrofo ('), ponto (.), hífen (-), barra (/), parênteses e vírgula"
)


@dataclass(frozen=True)
class ErroBusca:
    """Campo da tela que causou o erro e a mensagem para mostrar."""

    campo: str
    mensagem: str


def limpar_termo(valor: str) -> str:
    """'  Maria   da Silva ' -> 'Maria da Silva'."""
    return " ".join(valor.split())


def normalizar_texto(valor: str) -> str:
    """'  José   d'Ávila ' -> "JOSE D'AVILA", como normalize_text do backend."""
    decomposto = unicodedata.normalize("NFKD", valor)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.split()).upper()


def _validar_texto(valor: str, rotulo: str, padrao: re.Pattern[str], caracteres: str) -> str | None:
    normalizado = normalizar_texto(valor)
    if not TEXTO_MIN_CHARS <= len(normalizado) <= TEXTO_MAX_CHARS:
        return f"O {rotulo} deve ter de {TEXTO_MIN_CHARS} a {TEXTO_MAX_CHARS} caracteres."
    if not padrao.fullmatch(normalizado):
        return f"Use só {caracteres} no {rotulo}."
    if SEQUENCIA_PROIBIDA in normalizado:
        return "Não use dois hífens seguidos (--)."
    return None


def validar_busca(busca: Busca) -> ErroBusca | None:
    """Primeiro erro da busca, na ordem em que a API confere, ou None se pode enviar."""
    if busca.nome and busca.similar:
        return ErroBusca("termo", "Use nome exato ou nome parecido, não os dois.")
    if not any((busca.nome, busca.similar, busca.cargo, busca.orgao, busca.uf)):
        return ErroBusca("termo", "Informe um nome ou ao menos um filtro: cargo, órgão ou UF.")

    if busca.nome:
        mensagem = _validar_texto(busca.nome, "nome", NOME_PERMITIDO, CARACTERES_NOME)
        if mensagem is not None:
            return ErroBusca("termo", mensagem)

    if busca.similar:
        mensagem = _validar_texto(
            busca.similar, "nome parecido", SIMILAR_PERMITIDO, CARACTERES_SIMILAR
        )
        if mensagem is not None:
            return ErroBusca("termo", mensagem)
        if LETRAS_SEGUIDAS.search(normalizar_texto(busca.similar)) is None:
            return ErroBusca("termo", MENSAGEM_LETRAS_SEGUIDAS)
        if not LIMITE_MIN <= busca.limite <= LIMITE_MAX:
            return ErroBusca("limite", f"O limite deve estar entre {LIMITE_MIN} e {LIMITE_MAX}.")

    for campo, rotulo, valor in (("cargo", "cargo", busca.cargo), ("orgao", "órgão", busca.orgao)):
        if valor:
            mensagem = _validar_texto(valor, rotulo, CARGO_ORGAO_PERMITIDO, CARACTERES_CARGO_ORGAO)
            if mensagem is not None:
                return ErroBusca(campo, mensagem)

    if busca.uf and busca.uf not in UFS:
        return ErroBusca("uf", "Escolha uma UF válida.")
    if busca.uf and busca.situacao is Situacao.APOSENTADO:
        # A API responde 404 para essa combinação: a fonte dos aposentados não traz UF.
        return ErroBusca(
            "uf",
            "Aposentados não têm UF na fonte. Para filtrar por UF, escolha a situação "
            "Ativo ou Todos.",
        )

    if not PAGINA_MIN <= busca.pagina <= PAGINA_MAX:
        return ErroBusca("pagina", f"A página deve estar entre {PAGINA_MIN} e {PAGINA_MAX}.")
    if not POR_PAGINA_MIN <= busca.por_pagina <= POR_PAGINA_MAX:
        return ErroBusca(
            "por_pagina",
            f"Escolha de {POR_PAGINA_MIN} a {POR_PAGINA_MAX} resultados por página.",
        )
    return None
