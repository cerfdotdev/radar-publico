"""Linha de comando do app desktop."""

import argparse

from .app import run
from .config import API_URL_ENV, DEFAULT_API_URL, api_url_do_ambiente, validar_url
from .verificacao import verificar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Radar Público — consulta de servidores federais")
    parser.add_argument(
        "--api-url",
        default=api_url_do_ambiente(),
        help=f"URL base da API (padrão: variável {API_URL_ENV} ou {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="abre a janela fora da tela, consulta <api>/health e sai; testa o executável",
    )
    args = parser.parse_args(argv)
    try:
        api_url = validar_url(args.api_url)
    except ValueError as erro:
        parser.error(str(erro))
    if args.verificar:
        return verificar(api_url)
    return run(api_url)
