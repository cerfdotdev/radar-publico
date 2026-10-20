"""Inicialização do aplicativo Qt."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from .window import MainWindow


def criar_aplicacao(argv: Sequence[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("Radar Público")
    app.setOrganizationName("Radar Público")
    return app


def run(api_url: str | None = None, argv: Sequence[str] | None = None) -> int:
    app = criar_aplicacao(argv)
    janela = MainWindow(api_url=api_url)
    janela.show()
    return app.exec()


create_app = criar_aplicacao
