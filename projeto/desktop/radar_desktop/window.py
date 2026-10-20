"""Janela principal do Radar Público para desktop (PySide6)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .api import (
    LIMITE_MAX,
    LIMITE_MIN,
    LIMITE_PADRAO,
    POR_PAGINA_OPCOES,
    POR_PAGINA_PADRAO,
    ApiError,
    Busca,
    RadarApiClient,
)
from .validacao import UFS, limpar_termo, validar_busca

SITUACOES = {"ativo": "Ativo", "aposentado": "Aposentado"}


def formatar_moeda(valor: object) -> str:
    if not isinstance(valor, (int, float)):
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _SinaisBusca(QObject):
    resultado = Signal(object)
    erro = Signal(str)


class _BuscaWorker(QRunnable):
    """Faz a requisição fora da thread da interface."""

    def __init__(self, client: RadarApiClient, busca: Busca, sinais: _SinaisBusca) -> None:
        super().__init__()
        self.client = client
        self.busca = busca
        self.sinais = sinais

    @Slot()
    def run(self) -> None:
        try:
            self.sinais.resultado.emit(self.client.buscar(self.busca))
        except ApiError as erro:
            self.sinais.erro.emit(erro.mensagem)
        except Exception:
            self.sinais.erro.emit("Ocorreu um erro inesperado ao consultar a API.")


class MainWindow(QMainWindow):
    """Tela de busca com os mesmos filtros do frontend web."""

    def __init__(
        self,
        api_url: str | None = None,
        client: RadarApiClient | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.client = client or RadarApiClient(api_url)
        self._pool = QThreadPool.globalInstance()
        self._sinais = _SinaisBusca()
        self._sinais.resultado.connect(self._mostrar_resultado)
        self._sinais.erro.connect(self._mostrar_erro)
        self._total_paginas = 1
        self._montar_interface()
        self._atualizar_modo()
        self._atualizar_titulo()

    # ------------------------------------------------------------------ UI
    def _montar_interface(self) -> None:
        self.setMinimumSize(900, 620)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Radar Público")
        titulo.setObjectName("titulo")
        fonte = titulo.font()
        fonte.setPointSize(fonte.pointSize() + 8)
        fonte.setBold(True)
        titulo.setFont(fonte)
        layout.addWidget(titulo)

        self.url_label = QLabel()
        self.url_label.setObjectName("urlApi")
        self.url_label.setStyleSheet("color: #4E4643;")
        layout.addWidget(self.url_label)

        formulario = QFormLayout()
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.campo_nome = QLineEdit()
        self.campo_nome.setObjectName("nome")
        self.campo_nome.setAccessibleName("Nome do servidor")
        self.campo_nome.setPlaceholderText("Ex.: Maria da Silva")
        self.campo_nome.returnPressed.connect(self.buscar)

        linha_nome = QHBoxLayout()
        linha_nome.addWidget(self.campo_nome, 1)
        self.modo = QComboBox()
        self.modo.setObjectName("modo")
        self.modo.setAccessibleName("Como buscar o nome")
        self.modo.addItem("Nome exato", "exato")
        self.modo.addItem("Nome parecido", "similar")
        self.modo.currentIndexChanged.connect(self._atualizar_modo)
        linha_nome.addWidget(self.modo)
        formulario.addRow("Nome do servidor", linha_nome)

        self.limite = QSpinBox()
        self.limite.setObjectName("limite")
        self.limite.setAccessibleName("Limite de resultados")
        self.limite.setRange(LIMITE_MIN, LIMITE_MAX)
        self.limite.setValue(LIMITE_PADRAO)
        formulario.addRow("Limite (nome parecido)", self.limite)

        self.campo_cargo = QLineEdit()
        self.campo_cargo.setObjectName("cargo")
        self.campo_cargo.setAccessibleName("Cargo")
        self.campo_cargo.setPlaceholderText("Ex.: professor")
        self.campo_cargo.returnPressed.connect(self.buscar)
        formulario.addRow("Cargo", self.campo_cargo)

        self.campo_orgao = QLineEdit()
        self.campo_orgao.setObjectName("orgao")
        self.campo_orgao.setAccessibleName("Órgão")
        self.campo_orgao.setPlaceholderText("Nome ou sigla, ex.: INSS")
        self.campo_orgao.returnPressed.connect(self.buscar)
        formulario.addRow("Órgão", self.campo_orgao)

        self.campo_uf = QComboBox()
        self.campo_uf.setObjectName("uf")
        self.campo_uf.setAccessibleName("UF")
        self.campo_uf.addItem("Todas", "")
        for uf in UFS:
            self.campo_uf.addItem(uf, uf)
        formulario.addRow("UF (só ativos)", self.campo_uf)

        linha_pagina = QHBoxLayout()
        self.pagina = QSpinBox()
        self.pagina.setObjectName("pagina")
        self.pagina.setAccessibleName("Página")
        self.pagina.setRange(1, 10_000)
        self.pagina.setValue(1)
        linha_pagina.addWidget(self.pagina)
        self.por_pagina = QComboBox()
        self.por_pagina.setObjectName("porPagina")
        self.por_pagina.setAccessibleName("Resultados por página")
        for quantidade in POR_PAGINA_OPCOES:
            self.por_pagina.addItem(str(quantidade), quantidade)
        self.por_pagina.setCurrentIndex(POR_PAGINA_OPCOES.index(POR_PAGINA_PADRAO))
        linha_pagina.addWidget(self.por_pagina)
        formulario.addRow("Página / por página", linha_pagina)

        layout.addLayout(formulario)

        linha_botoes = QHBoxLayout()
        self.botao_buscar = QPushButton("Buscar")
        self.botao_buscar.setObjectName("buscar")
        self.botao_buscar.setAccessibleName("Buscar")
        self.botao_buscar.setDefault(True)
        self.botao_buscar.clicked.connect(self.buscar)
        self.botao_limpar = QPushButton("Limpar")
        self.botao_limpar.setObjectName("limpar")
        self.botao_limpar.clicked.connect(self.limpar)
        self.botao_anterior = QPushButton("Anterior")
        self.botao_anterior.setObjectName("anterior")
        self.botao_anterior.clicked.connect(lambda: self._ir_para_pagina(self.pagina.value() - 1))
        self.botao_proxima = QPushButton("Próxima")
        self.botao_proxima.setObjectName("proxima")
        self.botao_proxima.clicked.connect(lambda: self._ir_para_pagina(self.pagina.value() + 1))
        linha_botoes.addWidget(self.botao_buscar)
        linha_botoes.addWidget(self.botao_limpar)
        linha_botoes.addStretch(1)
        linha_botoes.addWidget(self.botao_anterior)
        linha_botoes.addWidget(self.botao_proxima)
        layout.addLayout(linha_botoes)

        self.status = QLabel("Informe um nome ou use os filtros para pesquisar.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setObjectName("resultados")
        self.tabela.setAccessibleName("Servidores encontrados")
        self.tabela.setHorizontalHeaderLabels(
            ["Nome", "Situação", "Cargo", "Órgão", "UF", "Valor (R$)"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.cellDoubleClicked.connect(self._abrir_detalhe)
        layout.addWidget(self.tabela, 1)

        self.setCentralWidget(central)
        self._desabilitar_paginacao()

        menu = self.menuBar().addMenu("Configurações")
        acao_url = QAction("URL da API…", self)
        acao_url.triggered.connect(self._alterar_url_api)
        menu.addAction(acao_url)

    def _atualizar_titulo(self) -> None:
        self.setWindowTitle(f"Radar Público — {self.client.api_url}")
        self.url_label.setText(f"API: {self.client.api_url}")

    def _atualizar_modo(self) -> None:
        similar = self.modo.currentData() == "similar"
        self.limite.setEnabled(similar)
        self.pagina.setEnabled(not similar)
        self.por_pagina.setEnabled(not similar)
        if similar:
            self.pagina.setValue(1)
            self._desabilitar_paginacao()
        self.campo_nome.setPlaceholderText(
            "Ex.: %MARIA%SILVA%" if similar else "Ex.: Maria da Silva"
        )

    # ------------------------------------------------------------- comandos
    def _montar_busca(self) -> Busca:
        termo = limpar_termo(self.campo_nome.text())
        similar = self.modo.currentData() == "similar"
        return Busca(
            nome="" if similar else termo,
            similar=termo if similar else "",
            limite=self.limite.value(),
            cargo=limpar_termo(self.campo_cargo.text()),
            orgao=limpar_termo(self.campo_orgao.text()),
            uf=str(self.campo_uf.currentData() or ""),
            pagina=self.pagina.value(),
            por_pagina=int(self.por_pagina.currentData()),
        )

    def buscar(self) -> None:
        busca = self._montar_busca()
        erro = validar_busca(busca)
        if erro is not None:
            self._mostrar_erro(erro.mensagem)
            return

        self._definir_ocupado(True)
        self.status.setText("Buscando…")
        self.tabela.setRowCount(0)
        self._desabilitar_paginacao()
        self._pool.start(_BuscaWorker(self.client, busca, self._sinais))

    def limpar(self) -> None:
        self.campo_nome.clear()
        self.campo_cargo.clear()
        self.campo_orgao.clear()
        self.campo_uf.setCurrentIndex(0)
        self.modo.setCurrentIndex(0)
        self.limite.setValue(LIMITE_PADRAO)
        self.pagina.setValue(1)
        self.por_pagina.setCurrentIndex(POR_PAGINA_OPCOES.index(POR_PAGINA_PADRAO))
        self.tabela.setRowCount(0)
        self._total_paginas = 1
        self._desabilitar_paginacao()
        self.status.setText("Informe um nome ou use os filtros para pesquisar.")

    def _ir_para_pagina(self, pagina: int) -> None:
        if 1 <= pagina <= self._total_paginas:
            self.pagina.setValue(pagina)
            self.buscar()

    def set_api_url(self, url: str) -> None:
        self.client = RadarApiClient(url)
        self._atualizar_titulo()
        self.status.setText("URL da API atualizada.")

    def _alterar_url_api(self) -> None:
        url, confirmou = QInputDialog.getText(
            self,
            "URL da API",
            "Endereço do backend (com ou sem /api):",
            text=self.client.base_url,
        )
        if confirmou and url.strip():
            self.set_api_url(url.strip())

    # ------------------------------------------------------------- respostas
    def _definir_ocupado(self, ocupado: bool) -> None:
        self.botao_buscar.setEnabled(not ocupado)
        self.botao_buscar.setText("Buscando…" if ocupado else "Buscar")
        self.botao_limpar.setEnabled(not ocupado)
        self.campo_nome.setReadOnly(ocupado)

    def _mostrar_resultado(self, dados: dict[str, Any]) -> None:
        self._definir_ocupado(False)
        itens = dados.get("data") if isinstance(dados.get("data"), list) else []
        meta = dados.get("meta") if isinstance(dados.get("meta"), dict) else {}
        self._total_paginas = max(1, int(meta.get("total_pages", 1) or 1))
        self.pagina.setValue(max(1, int(meta.get("page", 1) or 1)))
        self._preencher_tabela(itens)

        total = int(meta.get("total", len(itens)) or 0)
        if not itens:
            self.status.setText("Nenhum vínculo encontrado com os filtros informados.")
        else:
            prefixo = "Mais de 10.000" if meta.get("total_exato") is False else str(total)
            self.status.setText(
                f"{prefixo} resultado(s) encontrado(s) · página "
                f"{meta.get('page', 1)} de {meta.get('total_pages', 1)}"
            )
        self.botao_anterior.setEnabled(self.pagina.value() > 1)
        self.botao_proxima.setEnabled(self.pagina.value() < self._total_paginas)

    def _mostrar_erro(self, mensagem: str) -> None:
        self._definir_ocupado(False)
        self.status.setText(mensagem)
        self._desabilitar_paginacao()

    def _preencher_tabela(self, itens: list[dict[str, Any]]) -> None:
        self.tabela.setRowCount(len(itens))
        for linha, servidor in enumerate(itens):
            situacao = SITUACOES.get(str(servidor.get("situacao")), str(servidor.get("situacao") or "—"))
            orgao = servidor.get("orgao") or "—"
            if servidor.get("sigla_orgao"):
                orgao = f"{orgao} ({servidor['sigla_orgao']})"
            valores = [
                servidor.get("nome") or "—",
                situacao,
                servidor.get("cargo") or "—",
                orgao,
                servidor.get("uf") or "—",
                formatar_moeda(servidor.get("valor")),
            ]
            for coluna, valor in enumerate(valores):
                celula = QTableWidgetItem(str(valor))
                if coluna == 0:
                    celula.setData(Qt.ItemDataRole.UserRole, servidor.get("id"))
                if coluna == 5:
                    celula.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabela.setItem(linha, coluna, celula)

    def _desabilitar_paginacao(self) -> None:
        self.botao_anterior.setEnabled(False)
        self.botao_proxima.setEnabled(False)

    def _abrir_detalhe(self, linha: int, _coluna: int) -> None:
        celula = self.tabela.item(linha, 0)
        if celula is None:
            return
        servidor_id = celula.data(Qt.ItemDataRole.UserRole)
        if servidor_id is None:
            return
        try:
            servidor = self.client.detalhar(int(servidor_id))
        except ApiError as erro:
            QMessageBox.warning(self, "Detalhe indisponível", erro.mensagem)
            return
        except Exception:
            QMessageBox.warning(self, "Detalhe indisponível", "Não foi possível carregar o detalhe.")
            return

        linhas = [
            f"Nome: {servidor.get('nome') or '—'}",
            f"Situação: {SITUACOES.get(str(servidor.get('situacao')), '—')}",
            f"Cargo: {servidor.get('cargo') or '—'}",
            f"Órgão: {servidor.get('orgao') or '—'}",
            f"UF: {servidor.get('uf') or 'não informada'}",
            f"Valor: {formatar_moeda(servidor.get('valor'))}",
            f"Referência: {servidor.get('referencia') or '—'}",
        ]
        if servidor.get("tipo_aposentadoria"):
            linhas.append(f"Tipo de aposentadoria: {servidor['tipo_aposentadoria']}")
        if servidor.get("portaria"):
            linhas.append(f"Portaria: {servidor['portaria']}")
        QMessageBox.information(self, "Detalhe do vínculo", "\n".join(linhas))


JanelaPrincipal = MainWindow
