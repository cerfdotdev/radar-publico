"""Atalho para abrir a janela do app; o pacote fica em radar_desktop."""

try:
    from radar_desktop.app import create_app, criar_aplicacao, run
    from radar_desktop.window import JanelaPrincipal, MainWindow
except ModuleNotFoundError:  # importado como projeto.desktop.app
    from .radar_desktop.app import create_app, criar_aplicacao, run
    from .radar_desktop.window import JanelaPrincipal, MainWindow

__all__ = ["MainWindow", "JanelaPrincipal", "create_app", "criar_aplicacao", "run"]

if __name__ == "__main__":
    raise SystemExit(run())
