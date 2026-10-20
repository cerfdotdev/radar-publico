"""Ficha de um vínculo: abre com os dados da lista e completa com GET /api/servidores/<id>.

Se o detalhe não chegar, a ficha continua com os dados da lista, como no frontend web.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from .api import Detalhe, Servidor, Situacao
from .estilo import Tom, definir_aviso, rotulo_texto
from .formatacao import (
    ROTULOS_SITUACAO,
    SEM_VALOR,
    formatar_data,
    formatar_moeda,
    formatar_orgao,
    formatar_referencia,
    texto_ou_travessao,
)

LARGURA_MIN = 600
ESPACO = 12
CARREGANDO = "…"
INDISPONIVEL = "Indisponível"
MENSAGEM_CARREGANDO = "Carregando os dados completos do vínculo…"
UF_APOSENTADO = "Não informada — o conjunto de aposentados não traz UF"

# (campo, rótulo) na ordem da ficha; os do detalhe dependem da situação.
CAMPOS_LISTA = (
    ("situacao", "Situação"),
    ("valor", "Valor"),
    ("cargo", "Cargo"),
    ("orgao", "Órgão"),
    ("sigla_orgao", "Sigla do órgão"),
    ("uf", "UF"),
)
CAMPOS_APOSENTADORIA = (
    ("tipo_aposentadoria", "Tipo de aposentadoria"),
    ("fundamento_legal", "Fundamento legal"),
    ("portaria", "Portaria"),
    ("data_aposentadoria", "Data da aposentadoria"),
)
CAMPOS_CARREIRA = (("codigo_carreira", "Código da carreira"),)
CAMPOS_INGRESSO = (
    ("forma_ingresso", "Forma de ingresso"),
    ("data_ingresso", "Data de ingresso"),
    ("referencia", "Referência"),
)


class DialogoDetalhe(QDialog):
    def __init__(self, servidor: Servidor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Detalhe do vínculo")
        self.setMinimumWidth(LARGURA_MIN)
        aposentado = servidor.situacao is Situacao.APOSENTADO

        layout = QVBoxLayout(self)
        layout.setSpacing(ESPACO)
        layout.addWidget(rotulo_texto(servidor.nome, "tituloDetalhe"))
        resumo = f"{servidor.cargo or 'Cargo não informado'} · "
        resumo += formatar_orgao(servidor.orgao, servidor.sigla_orgao)
        layout.addWidget(rotulo_texto(resumo, "aux"))

        self.aviso = rotulo_texto(nome="aviso")
        self.aviso.setAccessibleName("Situação do carregamento")
        definir_aviso(self.aviso, MENSAGEM_CARREGANDO, Tom.NEUTRO)
        layout.addWidget(self.aviso)

        campos_detalhe = (CAMPOS_APOSENTADORIA if aposentado else CAMPOS_CARREIRA) + CAMPOS_INGRESSO
        self._campos_detalhe = tuple(campo for campo, _ in campos_detalhe)
        self._valores: dict[str, QLabel] = {}
        formulario = QFormLayout()
        formulario.setHorizontalSpacing(ESPACO * 2)
        for campo, rotulo in CAMPOS_LISTA + campos_detalhe:
            if campo == "valor":
                rotulo = "Valor da aposentadoria" if aposentado else "Remuneração"
            valor = rotulo_texto(CARREGANDO)
            valor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            titulo = QLabel(rotulo)
            titulo.setObjectName("rotulo")
            formulario.addRow(titulo, valor)
            self._valores[campo] = valor
        layout.addLayout(formulario)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

        self._preencher(servidor)

    def _preencher(self, servidor: Servidor) -> None:
        aposentado = servidor.situacao is Situacao.APOSENTADO
        textos = {
            "situacao": ROTULOS_SITUACAO[servidor.situacao],
            "valor": formatar_moeda(servidor.valor),
            "cargo": texto_ou_travessao(servidor.cargo),
            "orgao": servidor.orgao,
            "sigla_orgao": texto_ou_travessao(servidor.sigla_orgao),
            "uf": servidor.uf or (UF_APOSENTADO if aposentado else SEM_VALOR),
        }
        if isinstance(servidor, Detalhe):
            textos |= {
                "codigo_carreira": texto_ou_travessao(servidor.codigo_carreira),
                "tipo_aposentadoria": texto_ou_travessao(servidor.tipo_aposentadoria),
                "fundamento_legal": texto_ou_travessao(servidor.fundamento_legal),
                "portaria": texto_ou_travessao(servidor.portaria),
                "data_aposentadoria": formatar_data(servidor.data_aposentadoria),
                "forma_ingresso": texto_ou_travessao(servidor.forma_ingresso),
                "data_ingresso": formatar_data(servidor.data_ingresso),
                "referencia": formatar_referencia(servidor.referencia),
            }
        for campo, texto in textos.items():
            if campo in self._valores:
                self._valores[campo].setText(texto)

    def mostrar_detalhe(self, detalhe: Detalhe) -> None:
        self._preencher(detalhe)
        self.aviso.hide()

    def mostrar_falha(self, mensagem: str) -> None:
        for campo in self._campos_detalhe:
            self._valores[campo].setText(INDISPONIVEL)
        definir_aviso(
            self.aviso,
            f"Não foi possível carregar os dados completos do vínculo. {mensagem} "
            "Os dados abaixo vêm da lista de resultados.",
            Tom.ATENCAO,
        )
