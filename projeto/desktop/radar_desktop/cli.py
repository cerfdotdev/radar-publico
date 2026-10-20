"""Linha de comando do app desktop."""

import argparse

from .app import run
from .config import API_URL_ENV, DEFAULT_API_URL, api_url_do_ambiente, validar_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Radar Público — consulta de servidores federais")
    parser.add_argument(
        "--api-url",
        default=api_url_do_ambiente(),
        help=f"URL base da API (padrão: variável {API_URL_ENV} ou {DEFAULT_API_URL})",
    )
    args = parser.parse_args(argv)
    try:
        api_url = validar_url(args.api_url)
    except ValueError as erro:
        parser.error(str(erro))
    return run(api_url)
