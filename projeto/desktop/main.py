"""Ponto de entrada do app desktop: python main.py [--api-url URL]."""

import sys

from radar_desktop.cli import main

if __name__ == "__main__":
    sys.exit(main())
