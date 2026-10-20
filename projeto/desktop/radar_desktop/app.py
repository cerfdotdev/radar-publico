"""Inicialização do aplicativo Qt."""

import sys
from collections.abc import Sequence

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from .api import RadarApiClient
from .estilo import ESTILO_QT, FOLHA_DE_ESTILO, FONTE_FAMILIA, FONTE_TAMANHO_PT, PRIMARIA
from .window import MainWindow

NOME_APP = "Radar Público"


def criar_aplicacao(argv: Sequence[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(NOME_APP)
    app.setStyle(ESTILO_QT)
    # Seleção e foco dos controles desenhados pelo Fusion na cor da marca.
    paleta = app.palette()
    paleta.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARIA))
    app.setPalette(paleta)
    if FONTE_FAMILIA in QFontDatabase.families():
        app.setFont(QFont(FONTE_FAMILIA, FONTE_TAMANHO_PT))
    app.setStyleSheet(FOLHA_DE_ESTILO)
    return app


def run(api_url: str) -> int:
    app = criar_aplicacao()
    janela = MainWindow(RadarApiClient(api_url))
    janela.show()
    return app.exec()
