"""Configuração do app desktop: endereço da API escolhido fora do código."""

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

# Base da API como em docs/api.md (backend do Docker Compose).
DEFAULT_API_URL = "http://localhost:5000/api"
API_URL_ENV = "RADAR_API_URL"
ESQUEMAS_PERMITIDOS = ("http", "https")


def validar_url(url: str) -> str:
    """Devolve a URL sem espaços e sem / no fim; recusa o que não for http(s) com host."""
    limpa = url.strip().rstrip("/")
    partes = urlsplit(limpa)
    try:
        partes.port  # levanta ValueError se a porta não for um número válido
    except ValueError:
        porta_valida = False
    else:
        porta_valida = True
    if partes.scheme not in ESQUEMAS_PERMITIDOS or not partes.hostname or not porta_valida:
        raise ValueError(
            f"URL da API inválida: '{url.strip()}'. Use http:// ou https://, "
            f"por exemplo {DEFAULT_API_URL}."
        )
    return limpa


def api_url_do_ambiente(ambiente: Mapping[str, str] | None = None) -> str:
    """URL da variável RADAR_API_URL, ou o backend local do Docker Compose."""
    valores = os.environ if ambiente is None else ambiente
    return valores.get(API_URL_ENV, "").strip() or DEFAULT_API_URL
