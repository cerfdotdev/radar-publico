"""Atalho de importação da janela principal."""

try:
    from radar_desktop.window import JanelaPrincipal, MainWindow, formatar_moeda
except ModuleNotFoundError:  # importado como projeto.desktop.window
    from .radar_desktop.window import JanelaPrincipal, MainWindow, formatar_moeda

__all__ = ["MainWindow", "JanelaPrincipal", "formatar_moeda"]
