"""Ponto de entrada do app desktop."""

from __future__ import annotations

import sys

try:
    from radar_desktop.cli import main
except ModuleNotFoundError:  # importado como projeto.desktop.main
    from .radar_desktop.cli import main

if __name__ == "__main__":
    sys.exit(main())
