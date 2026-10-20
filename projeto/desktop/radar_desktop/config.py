"""Configuração do app desktop: endereço da API escolhido fora do código."""

import os

DEFAULT_API_URL = "http://localhost:5000"
API_URL_ENV = "RADAR_API_URL"
# Aliases aceitos para não obrigar quem já usa outro nome no ambiente.
API_URL_ENV_ALIASES = (
    "RADAR_PUBLICO_API_URL",
    "RADAR_API_BASE_URL",
    "API_BASE_URL",
    "API_URL",
)


def api_url_from_env(environ: dict[str, str] | None = None) -> str:
    """URL da API vinda do ambiente, ou o backend local do Docker Compose."""
    valores = os.environ if environ is None else environ
    for nome in (API_URL_ENV, *API_URL_ENV_ALIASES):
        valor = valores.get(nome, "").strip()
        if valor:
            return valor
    return DEFAULT_API_URL
