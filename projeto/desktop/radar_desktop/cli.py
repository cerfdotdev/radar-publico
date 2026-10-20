"""CLI e ponto de entrada do pacote desktop."""

from __future__ import annotations

import argparse

from .app import run
from .config import api_url_from_env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Radar Público — consulta de servidores federais")
    parser.add_argument(
        "--api-url",
        default=api_url_from_env(),
        help="URL do backend (padrão: RADAR_API_URL ou http://localhost:5000)",
    )
    args = parser.parse_args(argv)
    return run(api_url=args.api_url)
