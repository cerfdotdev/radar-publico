"""Validação e normalização dos parâmetros de GET /api/servidores (docs/api.md).

Toda entrada é validada aqui, antes de qualquer consulta ao banco. Textos são
normalizados como os dados da carga: maiúsculas, sem acento e com espaços simples.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus

from werkzeug.datastructures import MultiDict

from app.errors import ApiError

MIN_TEXT_LENGTH = 2
MAX_TEXT_LENGTH = 100
DEFAULT_PAGE = 1
MIN_PAGE = 1
DEFAULT_PER_PAGE = 20
MIN_PER_PAGE = 1
MAX_PER_PAGE = 100
# A contagem para em 10.000 resultados e só essas páginas existem (docs/banco.md).
MAX_TOTAL = 10_000
# Quanto da entrada inválida é repetido na mensagem de erro.
MAX_ECHOED_INPUT = 10
MAX_PAGE = math.ceil(MAX_TOTAL / MIN_PER_PAGE)

DEFAULT_LIMIT = 100
MIN_LIMIT = 1
MAX_LIMIT = 100
MIN_SIMILAR_LETTERS = 3
# GET /api/servidores/<id>: o id é bigint (projeto/db/init/01-schema.sql).
MIN_ID = 1
MAX_ID = 9_223_372_036_854_775_807

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)  # fmt: skip

# Depois da normalização: nomes só com letras, espaço, ' . -; cargo e órgão também
# com dígitos, / ( ) e vírgula, que aparecem nos nomes reais.
# Similar aceita '%' como curinga além dos mesmos caracteres do nome.
NOME_PATTERN = re.compile(r"[A-Z .'-]+")
CARGO_ORGAO_PATTERN = re.compile(r"[A-Z0-9 .'/(),-]+")
SIMILAR_PATTERN = re.compile(r"[A-Z .'%-]+")
FORBIDDEN_SEQUENCE = "--"
# Aspas em volta do valor, como no exemplo do enunciado: similar="%NOME%" ou ”%NOME%”.
QUOTE_MARKS = frozenset('"“”')
_QUOTE_CLASS = "[" + "".join(sorted(QUOTE_MARKS)) + "]"
QUOTED_VALUE = re.compile(rf"\s*{_QUOTE_CLASS}(.*){_QUOTE_CLASS}\s*", re.DOTALL)

SIMILARITY_PARAMS = ("similar", "limit")
PAGING_PARAMS = ("page", "per_page")
KNOWN_PARAMS = frozenset(
    {"nome", "cargo", "orgao", "uf", "situacao", *PAGING_PARAMS, *SIMILARITY_PARAMS}
)
FILTER_PARAMS = ("nome", "similar", "cargo", "orgao", "uf")


class Situacao(StrEnum):
    ATIVO = "ativo"
    APOSENTADO = "aposentado"
    TODOS = "todos"


@dataclass(frozen=True)
class SearchParams:
    nome: str | None
    similar: str | None
    limit: int
    cargo: str | None
    orgao: str | None
    uf: str | None
    situacao: Situacao
    page: int
    per_page: int


def invalid(message: str, code: str = "PARAMETRO_INVALIDO") -> ApiError:
    return ApiError(code, message, HTTPStatus.BAD_REQUEST)


def normalize_text(value: str) -> str:
    """'  Maria   José ' -> 'MARIA JOSE' (sem acento, maiúsculas, espaços simples)."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.split()).upper()


def strip_quotes(value: str) -> str:
    """'"%MARIA%"' -> '%MARIA%': tira um par de aspas em volta do valor, se houver."""
    quoted = QUOTED_VALUE.fullmatch(value)
    return value if quoted is None else quoted.group(1)


def parse_text(args: MultiDict, name: str, pattern: re.Pattern[str]) -> str | None:
    raw = args.get(name)
    if raw is None:
        return None
    value = normalize_text(strip_quotes(raw))
    if not MIN_TEXT_LENGTH <= len(value) <= MAX_TEXT_LENGTH:
        raise invalid(f"'{name}' deve ter de {MIN_TEXT_LENGTH} a {MAX_TEXT_LENGTH} caracteres.")
    if not pattern.fullmatch(value) or FORBIDDEN_SEQUENCE in value:
        raise invalid(f"'{name}' contém caracteres não permitidos.")
    return value


def parse_similar(args: MultiDict) -> str | None:
    """Valida e normaliza o padrão de similaridade; mantém '%' como curinga."""
    raw = args.get("similar")
    if raw is None:
        return None
    value = normalize_text(strip_quotes(raw))
    if not MIN_TEXT_LENGTH <= len(value) <= MAX_TEXT_LENGTH:
        raise invalid(f"'similar' deve ter de {MIN_TEXT_LENGTH} a {MAX_TEXT_LENGTH} caracteres.")
    if not SIMILAR_PATTERN.fullmatch(value) or FORBIDDEN_SEQUENCE in value:
        raise invalid("'similar' contém caracteres não permitidos.")
    letters_count = sum(1 for c in value if c.isalpha())
    if letters_count < MIN_SIMILAR_LETTERS:
        raise invalid(f"'similar' precisa de pelo menos {MIN_SIMILAR_LETTERS} letras fora dos '%'.")
    return value


def parse_int(args: MultiDict, name: str, default: int, minimum: int, maximum: int) -> int:
    raw = args.get(name)
    if raw is None:
        return default
    return to_int(name, raw, minimum, maximum)


def to_int(name: str, raw: str, minimum: int, maximum: int) -> int:
    raw = raw.strip()
    if not raw.isascii() or not raw.isdigit():
        raise invalid(f"'{name}' deve ser um número inteiro.")
    value = int(raw)
    if not minimum <= value <= maximum:
        raise invalid(f"'{name}' deve estar entre {minimum} e {maximum}.")
    return value


def parse_uf(args: MultiDict) -> str | None:
    raw = args.get("uf")
    if raw is None:
        return None
    uf = raw.strip().upper()
    if uf not in UFS:
        raise ApiError(
            "UF_INVALIDA",
            f"UF '{uf[:MAX_ECHOED_INPUT]}' não existe. Use uma das {len(UFS)} siglas.",
            HTTPStatus.BAD_REQUEST,
        )
    return uf


def parse_situacao(args: MultiDict) -> Situacao:
    raw = args.get("situacao", Situacao.TODOS).strip().lower()
    try:
        return Situacao(raw)
    except ValueError:
        options = ", ".join(s.value for s in Situacao)
        raise invalid(f"'situacao' deve ser uma destas: {options}.") from None


def parse_search_params(args: MultiDict) -> SearchParams:
    """Valida a query string inteira; levanta ApiError com o código do contrato."""
    unknown = sorted(set(args) - KNOWN_PARAMS)
    if unknown:
        raise invalid(f"Parâmetro desconhecido: {', '.join(unknown)}.", "PARAMETRO_DESCONHECIDO")

    if "nome" in args and "similar" in args:
        raise invalid("Os parâmetros 'nome' e 'similar' não podem ser usados juntos.")

    if "limit" in args and "similar" not in args:
        raise invalid("'limit' só pode ser usado com 'similar'.")

    paging = [name for name in PAGING_PARAMS if name in args]
    if paging and "similar" in args:
        raise invalid(
            f"'{paging[0]}' não pode ser usado com 'similar': a busca por similaridade não "
            "tem páginas e devolve até 'limit' resultados."
        )

    if not any(name in args for name in FILTER_PARAMS):
        raise invalid(
            "Informe pelo menos um filtro: nome, similar, cargo, orgao ou uf.",
            "FILTRO_OBRIGATORIO",
        )

    return SearchParams(
        nome=parse_text(args, "nome", NOME_PATTERN),
        similar=parse_similar(args),
        limit=parse_int(args, "limit", DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT),
        cargo=parse_text(args, "cargo", CARGO_ORGAO_PATTERN),
        orgao=parse_text(args, "orgao", CARGO_ORGAO_PATTERN),
        uf=parse_uf(args),
        situacao=parse_situacao(args),
        page=parse_int(args, "page", DEFAULT_PAGE, MIN_PAGE, MAX_PAGE),
        per_page=parse_int(args, "per_page", DEFAULT_PER_PAGE, MIN_PER_PAGE, MAX_PER_PAGE),
    )


def parse_servidor_id(raw_id: str, args: MultiDict) -> int:
    """Id de GET /api/servidores/<id>; a rota não aceita parâmetros na query string."""
    if args:
        unknown = ", ".join(sorted(args))
        raise invalid(f"Parâmetro desconhecido: {unknown}.", "PARAMETRO_DESCONHECIDO")
    return to_int("id", raw_id, MIN_ID, MAX_ID)
