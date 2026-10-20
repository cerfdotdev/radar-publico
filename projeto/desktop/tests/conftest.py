"""Configuração comum dos testes do desktop."""

import os

# Os testes da janela rodam sem tela (CI e terminal); precisa valer antes de importar o Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
