"""Aparência do app: cores de docs/DESIGN.md, folha de estilo Qt e tons dos avisos."""

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

# O mesmo visual em Windows, Linux e macOS.
ESTILO_QT = "Fusion"
# Usada se estiver instalada; senão fica a fonte padrão do sistema.
FONTE_FAMILIA = "IBM Plex Sans"
FONTE_TAMANHO_PT = 10
# Altura mínima dos campos. Listas e números ficam com o desenho do Fusion (a folha de
# estilo só nos campos de texto), porque bordas via QSS apagam as setas desses controles.
ALTURA_CAMPO_PX = 36

# Hex de referência dos tokens OKLCH de docs/DESIGN.md (o Qt não lê OKLCH).
FUNDO = "#FFFFFF"
SUPERFICIE = "#F9F6F5"
LINHA = "#E3DCDA"
LINHA_FORTE = "#8D8481"
TINTA = "#201916"
TINTA_2 = "#4E4643"
APAGADO = "#6A615E"
PRIMARIA = "#9E441D"
PRIMARIA_HOVER = "#873611"
PRIMARIA_SUAVE = "#FEECE5"
INFO_FUNDO, INFO_TEXTO, INFO_LINHA = "#E6F4FE", "#00476D", "#BAD5E9"
ATENCAO_FUNDO, ATENCAO_TEXTO, ATENCAO_LINHA = "#FFF2D6", "#694413", "#E9CD9D"
ERRO_FUNDO, ERRO_TEXTO, ERRO_LINHA = "#FFECEE", "#A71F43", "#F2BEC3"


class Tom(StrEnum):
    """Tom do aviso (docs/DESIGN.md): informação (429), atenção (> 10.000) e erro."""

    NEUTRO = "neutro"
    INFO = "info"
    ATENCAO = "atencao"
    ERRO = "erro"


FOLHA_DE_ESTILO = f"""
QMainWindow, QDialog, QWidget#central {{ background: {FUNDO}; color: {TINTA}; }}
QLabel {{ color: {TINTA}; }}
QLabel#titulo {{ font-size: 26px; font-weight: 600; }}
QLabel#tituloDetalhe {{ font-size: 20px; font-weight: 600; }}
QLabel#aux {{ color: {TINTA_2}; }}
QLabel#rotulo {{ font-weight: 600; }}

QWidget#formulario {{
    background: {SUPERFICIE}; border: 1px solid {LINHA}; border-radius: 10px;
}}
QLineEdit {{
    background: {FUNDO}; border: 1.5px solid {LINHA_FORTE}; border-radius: 8px;
    padding: 0 8px; min-height: {ALTURA_CAMPO_PX}px;
}}
QLineEdit:hover {{ border-color: {TINTA_2}; }}
QLineEdit:focus {{ border: 2px solid {PRIMARIA}; }}
QLineEdit[erro="true"] {{ border: 2px solid {ERRO_TEXTO}; background: {ERRO_FUNDO}; }}

QPushButton {{
    background: {FUNDO}; color: {TINTA}; border: 1.5px solid {LINHA_FORTE};
    border-radius: 8px; padding: 8px 18px;
}}
QPushButton:hover {{ background: {SUPERFICIE}; }}
QPushButton:focus {{ border: 2px solid {PRIMARIA}; }}
QPushButton:disabled {{ color: {APAGADO}; border-color: {LINHA}; }}
QPushButton#buscar {{
    background: {PRIMARIA}; color: {FUNDO}; border: 2px solid {PRIMARIA}; font-weight: 600;
}}
QPushButton#buscar:hover {{ background: {PRIMARIA_HOVER}; }}
QPushButton#buscar:focus {{ border: 2px solid {TINTA}; }}

QTableWidget {{
    border: 1px solid {LINHA}; border-radius: 8px; gridline-color: {LINHA};
    alternate-background-color: {SUPERFICIE};
    selection-background-color: {PRIMARIA_SUAVE}; selection-color: {TINTA};
}}
QHeaderView::section {{
    background: {SUPERFICIE}; color: {TINTA}; font-weight: 600; padding: 6px 8px;
    border: none; border-bottom: 1px solid {LINHA};
}}

QLabel#aviso {{ border-radius: 8px; padding: 10px 12px; border: 1px solid {LINHA}; }}
QLabel#aviso[tom="neutro"] {{ background: {FUNDO}; color: {TINTA_2}; }}
QLabel#aviso[tom="info"] {{
    background: {INFO_FUNDO}; color: {INFO_TEXTO}; border-color: {INFO_LINHA};
}}
QLabel#aviso[tom="atencao"] {{
    background: {ATENCAO_FUNDO}; color: {ATENCAO_TEXTO}; border-color: {ATENCAO_LINHA};
}}
QLabel#aviso[tom="erro"] {{
    background: {ERRO_FUNDO}; color: {ERRO_TEXTO}; border-color: {ERRO_LINHA};
}}
"""


def _repolir(widget: QWidget) -> None:
    """Reaplica a folha de estilo depois de mudar uma propriedade usada nos seletores."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def rotulo_texto(texto: str = "", nome: str = "") -> QLabel:
    """QLabel só de texto: o que vem da API nunca é interpretado como HTML."""
    rotulo = QLabel(texto)
    rotulo.setTextFormat(Qt.TextFormat.PlainText)
    rotulo.setWordWrap(True)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


def definir_aviso(rotulo: QLabel, texto: str, tom: Tom) -> None:
    rotulo.setText(texto)
    rotulo.setProperty("tom", tom.value)
    _repolir(rotulo)


def marcar_erro(widget: QWidget, com_erro: bool) -> None:
    widget.setProperty("erro", "true" if com_erro else "false")
    _repolir(widget)
