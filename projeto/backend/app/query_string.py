"""Query string lida como a pessoa digitou, inclusive com '%' sem codificar (docs/api.md).

No curl ou na barra do navegador, ?similar=%JOSE%DE%BARROS% chega com os '%' crus. O
Werkzeug decodifica todo %XY que forma UTF-8 válido, e '%DE%BA' vira U+07BA: a busca, que
devia achar JOSE DE BARROS, responderia 400. Aqui uma sequência %XY só é decodificada se
der um caractere que a API usa: ASCII, letra acentuada (a normalização tira o acento) ou
aspas tipográficas. As outras ficam como texto ('%DE%BA'). Os clientes que codificam o '%'
como %25 (web e desktop) não mudam. Bytes crus fora do UTF-8 viram U+FFFD, que a validação
recusa com 400, e não um 500.
"""

import re
import unicodedata

from flask import Request
from werkzeug.datastructures import MultiDict
from werkzeug.utils import cached_property

from app.search_params import QUOTE_MARKS

PERCENT_ESCAPES = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
ESCAPE_LENGTH = len("%XY")
MAX_UTF8_BYTES = 4
PAIR_SEPARATOR = "&"
KEY_SEPARATOR = "="
ENCODED_SPACE = "+"


def is_usable(char: str) -> bool:
    """Caractere que pode fazer sentido num parâmetro da API depois da normalização."""
    if char.isascii() or char in QUOTE_MARKS:
        return True
    decomposed = unicodedata.normalize("NFKD", char)
    return all(c.isascii() or unicodedata.combining(c) for c in decomposed)


def char_at(raw: bytes, start: int) -> str | None:
    """O caractere UTF-8 que começa em raw[start], ou None se ali não começa nenhum."""
    for end in range(start + 1, min(start + MAX_UTF8_BYTES, len(raw)) + 1):
        try:
            return raw[start:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return None


def decode_escapes(match: re.Match[str]) -> str:
    """Decodifica uma sequência de %XY, deixando como texto os que não dão caractere útil."""
    escaped = match.group()
    raw = bytes.fromhex(escaped.replace("%", ""))
    decoded: list[str] = []
    position = 0
    while position < len(raw):
        char = char_at(raw, position)
        if char is not None and is_usable(char):
            decoded.append(char)
            position += len(char.encode("utf-8"))
        else:
            start = position * ESCAPE_LENGTH
            decoded.append(escaped[start : start + ESCAPE_LENGTH])
            position += 1
    return "".join(decoded)


def unquote(text: str) -> str:
    return PERCENT_ESCAPES.sub(decode_escapes, text.replace(ENCODED_SPACE, " "))


def parse_query_string(query_string: bytes) -> list[tuple[str, str]]:
    """Pares (nome, valor) na ordem da URL; 'nome=' e 'nome' sozinho dão valor vazio."""
    text = query_string.decode("utf-8", errors="replace")
    pairs = []
    for part in text.split(PAIR_SEPARATOR):
        if part:
            key, _, value = part.partition(KEY_SEPARATOR)
            pairs.append((unquote(key), unquote(value)))
    return pairs


class ApiRequest(Request):
    """Request do Flask com request.args lido por parse_query_string."""

    @cached_property
    def args(self) -> MultiDict[str, str]:
        return self.parameter_storage_class(parse_query_string(self.query_string))
