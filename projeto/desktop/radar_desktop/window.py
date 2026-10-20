"""Janela principal do Radar Público para desktop: as mesmas buscas do frontend web.

As chamadas à API rodam no QThreadPool, fora da thread da interface. Cada busca
recebe um número de geração; a resposta de uma busca que já foi substituída por
outra (ou pelo Limpar) é descartada.
"""

import logging
from collections.abc import Callable
from dataclasses import replace
from functools import partial

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
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
    Detalhe,
    Meta,
    RadarApiClient,
    Resultado,
    Servidor,
    Situacao,
)
from .detalhe import DialogoDetalhe
from .estilo import ALTURA_CAMPO_PX, Tom, definir_aviso, marcar_erro, rotulo_texto
from .formatacao import (
    ROTULOS_SITUACAO,
    formatar_moeda,
    texto_intervalo,
    texto_ou_travessao,
    texto_total,
)
from .validacao import UFS, ErroBusca, limpar_termo, validar_busca

logger = logging.getLogger(__name__)

JANELA_LARGURA_MIN = 1040
JANELA_ALTURA_MIN = 700
MARGEM = 24
ESPACO = 12

MENSAGEM_INICIAL = "Informe um nome ou use os filtros de cargo, órgão e UF para pesquisar."
MENSAGEM_BUSCANDO = "Buscando…"
MENSAGEM_INESPERADA = "Ocorreu um erro inesperado ao consultar a API. Tente de novo."
TITULO_VAZIO = "Nenhum vínculo encontrado com os filtros informados."
DICA_VAZIO = "Confira a grafia ou remova algum filtro."
AVISO_TOTAL_LIMITADO = "Refine a busca: só os primeiros resultados podem ser paginados."
PLACEHOLDER_EXATO = "Ex.: Maria da Silva"
PLACEHOLDER_SIMILAR = "Ex.: %MARIA%SILVA%"

MODO_EXATO = "exato"
MODO_SIMILAR = "similar"
COLUNAS = ("Nome", "Situação", "Cargo", "Órgão", "Sigla", "UF", "Valor")
COLUNA_NOME = COLUNAS.index("Nome")
COLUNA_ORGAO = COLUNAS.index("Órgão")
COLUNA_VALOR = COLUNAS.index("Valor")


class _Sinais(QObject):
    """Leva a resposta da thread de trabalho para a thread da interface."""

    concluida = Signal(int, object)
    falhou = Signal(int, object)


class _Tarefa(QRunnable):
    """Uma chamada à API fora da thread da interface, marcada com a sua geração."""

    def __init__(self, geracao: int, chamada: Callable[[], object], sinais: _Sinais) -> None:
        super().__init__()
        self._geracao = geracao
        self._chamada = chamada
        self._sinais = sinais

    def run(self) -> None:
        try:
            resposta, ok = self._chamada(), True
        except ApiError as erro:
            resposta, ok = erro, False
        except Exception:
            # O cliente já converte rede, HTTP e formato em ApiError; isto só garante
            # que a tela nunca fique presa em "Buscando…".
            logger.exception("Falha inesperada na chamada à API")
            resposta, ok = ApiError(MENSAGEM_INESPERADA), False
        sinal = self._sinais.concluida if ok else self._sinais.falhou
        sinal.emit(self._geracao, resposta)


class MainWindow(QMainWindow):
    """Busca por nome exato ou parecido, filtros, paginação e detalhe do vínculo."""

    def __init__(self, client: RadarApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._pool = QThreadPool.globalInstance()
        # Sem pai: a tarefa mantém os sinais vivos mesmo se a janela fechar antes da resposta.
        self._sinais_busca = _Sinais()
        self._sinais_busca.concluida.connect(self._busca_concluida)
        self._sinais_busca.falhou.connect(self._busca_falhou)
        self._sinais_detalhe = _Sinais()
        self._sinais_detalhe.concluida.connect(self._detalhe_concluido)
        self._sinais_detalhe.falhou.connect(self._detalhe_falhou)
        self._geracao_busca = 0
        self._geracao_detalhe = 0
        self._ultima_busca: Busca | None = None
        self._meta: Meta | None = None
        self._servidores: tuple[Servidor, ...] = ()
        self._dialogo: DialogoDetalhe | None = None

        self._montar_interface()
        self._atualizar_modo()
        self._atualizar_url()

    # ------------------------------------------------------------------ interface
    def _montar_interface(self) -> None:
        self.setMinimumSize(JANELA_LARGURA_MIN, JANELA_ALTURA_MIN)
        central = QWidget(self)
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(MARGEM, MARGEM, MARGEM, MARGEM)
        layout.setSpacing(ESPACO)

        titulo = QLabel("Radar Público")
        titulo.setObjectName("titulo")
        layout.addWidget(titulo)
        self.url_label = rotulo_texto(nome="aux")
        layout.addWidget(self.url_label)

        self.formulario = QWidget()
        self.formulario.setObjectName("formulario")
        layout.addWidget(self.formulario)
        self._montar_formulario()

        botoes = QHBoxLayout()
        self.botao_buscar = QPushButton("&Buscar")
        self.botao_buscar.setObjectName("buscar")
        self.botao_buscar.clicked.connect(self.buscar)
        self.botao_limpar = QPushButton("Limpar")
        self.botao_limpar.clicked.connect(self.limpar)
        botoes.addWidget(self.botao_buscar)
        botoes.addWidget(self.botao_limpar)
        botoes.addStretch(1)
        layout.addLayout(botoes)

        self.aviso = rotulo_texto(nome="aviso")
        self.aviso.setAccessibleName("Situação da busca")
        definir_aviso(self.aviso, MENSAGEM_INICIAL, Tom.NEUTRO)
        layout.addWidget(self.aviso)

        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setAccessibleName("Servidores encontrados")
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for coluna in (COLUNA_NOME, COLUNA_ORGAO):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Stretch)
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setAlternatingRowColors(True)
        # Enter ou duplo clique numa linha abrem o detalhe.
        self.tabela.activated.connect(lambda indice: self._abrir_detalhe(indice.row()))
        self.tabela.itemSelectionChanged.connect(self._atualizar_botao_detalhe)
        layout.addWidget(self.tabela, 1)

        rodape = QHBoxLayout()
        self.botao_anterior = QPushButton("&Anterior")
        self.botao_anterior.clicked.connect(partial(self._ir_para_pagina, -1))
        self.rotulo_pagina = QLabel()
        self.botao_proxima = QPushButton("Pró&xima")
        self.botao_proxima.clicked.connect(partial(self._ir_para_pagina, 1))
        self.botao_detalhe = QPushButton("Ver &detalhe")
        self.botao_detalhe.clicked.connect(lambda: self._abrir_detalhe(self.tabela.currentRow()))
        rodape.addWidget(self.botao_anterior)
        rodape.addWidget(self.rotulo_pagina)
        rodape.addWidget(self.botao_proxima)
        rodape.addStretch(1)
        rodape.addWidget(self.botao_detalhe)
        layout.addLayout(rodape)

        self.setCentralWidget(central)
        self._atualizar_paginacao()
        self._atualizar_botao_detalhe()

        QWidget.setTabOrder(self.por_pagina, self.botao_buscar)
        for anterior, seguinte in (
            (self.botao_buscar, self.botao_limpar),
            (self.botao_limpar, self.tabela),
            (self.tabela, self.botao_anterior),
            (self.botao_anterior, self.botao_proxima),
            (self.botao_proxima, self.botao_detalhe),
        ):
            QWidget.setTabOrder(anterior, seguinte)

        menu = self.menuBar().addMenu("&Configurações")
        acao_url = QAction("URL da &API…", self)
        acao_url.triggered.connect(self._alterar_url_api)
        menu.addAction(acao_url)

    def _montar_formulario(self) -> None:
        grade = QGridLayout(self.formulario)
        grade.setContentsMargins(MARGEM, MARGEM, MARGEM, MARGEM)
        grade.setHorizontalSpacing(ESPACO)
        grade.setVerticalSpacing(ESPACO)

        self.campo_nome = QLineEdit()
        self.modo = QComboBox()
        self.modo.addItem("Nome exato", MODO_EXATO)
        self.modo.addItem("Nome parecido (com %)", MODO_SIMILAR)
        self.modo.currentIndexChanged.connect(self._atualizar_modo)
        self.limite = QSpinBox()
        self.limite.setRange(LIMITE_MIN, LIMITE_MAX)
        self.limite.setValue(LIMITE_PADRAO)
        self.campo_cargo = QLineEdit()
        self.campo_cargo.setPlaceholderText("Ex.: professor")
        self.campo_orgao = QLineEdit()
        self.campo_orgao.setPlaceholderText("Nome ou sigla, ex.: INSS")
        self.campo_uf = QComboBox()
        self.campo_uf.addItem("Todas", "")
        for uf in UFS:
            self.campo_uf.addItem(uf, uf)
        self.campo_situacao = QComboBox()
        for situacao, rotulo in (
            (Situacao.TODOS, "Todos"),
            (Situacao.ATIVO, ROTULOS_SITUACAO[Situacao.ATIVO]),
            (Situacao.APOSENTADO, ROTULOS_SITUACAO[Situacao.APOSENTADO]),
        ):
            self.campo_situacao.addItem(rotulo, situacao)
        self.por_pagina = QComboBox()
        for quantidade in POR_PAGINA_OPCOES:
            self.por_pagina.addItem(str(quantidade), quantidade)
        self.por_pagina.setCurrentIndex(POR_PAGINA_OPCOES.index(POR_PAGINA_PADRAO))

        # (rótulo com atalho Alt, campo), em duas colunas, na ordem do Tab.
        linhas = (
            (("&Nome do servidor", self.campo_nome), ("&Tipo de busca", self.modo)),
            (("&Cargo", self.campo_cargo), ("Ó&rgão", self.campo_orgao)),
            (("&UF (só ativos)", self.campo_uf), ("&Situação", self.campo_situacao)),
            (("&Limite (nome parecido)", self.limite), ("&Por página", self.por_pagina)),
        )
        anterior: QWidget | None = None
        for linha, pares in enumerate(linhas):
            for par, (texto, campo) in enumerate(pares):
                rotulo = QLabel(texto)
                rotulo.setObjectName("rotulo")
                rotulo.setBuddy(campo)
                grade.addWidget(rotulo, linha, par * 2)
                grade.addWidget(campo, linha, par * 2 + 1)
                if anterior is not None:
                    QWidget.setTabOrder(anterior, campo)
                anterior = campo
        grade.setColumnStretch(1, 1)
        grade.setColumnStretch(3, 1)
        for controle in (
            self.modo,
            self.campo_uf,
            self.campo_situacao,
            self.limite,
            self.por_pagina,
        ):
            controle.setMinimumHeight(ALTURA_CAMPO_PX)

        # Enter em qualquer campo do formulário busca; os botões ficam fora dele.
        for tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            atalho = QShortcut(QKeySequence(tecla), self.formulario)
            atalho.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atalho.activated.connect(self.buscar)

        self._campos_por_erro: dict[str, QWidget] = {
            "termo": self.campo_nome,
            "limite": self.limite,
            "cargo": self.campo_cargo,
            "orgao": self.campo_orgao,
            "uf": self.campo_uf,
            "por_pagina": self.por_pagina,
        }

    def _modo_similar(self) -> bool:
        return self.modo.currentData() == MODO_SIMILAR

    def _atualizar_modo(self) -> None:
        similar = self._modo_similar()
        self.limite.setEnabled(similar)
        # A busca por nome parecido não é paginada: devolve até 'limite' resultados.
        self.por_pagina.setEnabled(not similar)
        self.campo_nome.setPlaceholderText(PLACEHOLDER_SIMILAR if similar else PLACEHOLDER_EXATO)

    def _atualizar_url(self) -> None:
        self.setWindowTitle(f"Radar Público — {self.client.api_url}")
        self.url_label.setText(f"API: {self.client.api_url}")

    # ------------------------------------------------------------------ busca
    def _montar_busca(self) -> Busca:
        termo = limpar_termo(self.campo_nome.text())
        similar = self._modo_similar()
        return Busca(
            nome="" if similar else termo,
            similar=termo if similar else "",
            limite=self.limite.value(),
            cargo=limpar_termo(self.campo_cargo.text()),
            orgao=limpar_termo(self.campo_orgao.text()),
            uf=self.campo_uf.currentData(),
            situacao=Situacao(self.campo_situacao.currentData()),
            por_pagina=self.por_pagina.currentData(),
        )

    def buscar(self) -> None:
        """Nova busca com os valores do formulário, sempre a partir da primeira página."""
        busca = self._montar_busca()
        erro = validar_busca(busca)
        self._marcar_erro(erro)
        if erro is not None:
            # Uma busca inválida também substitui a que estava em andamento.
            self._geracao_busca += 1
            definir_aviso(self.aviso, erro.mensagem, Tom.ERRO)
            return
        self._executar(busca)

    def _executar(self, busca: Busca) -> None:
        self._geracao_busca += 1
        self._ultima_busca = busca
        self._meta = None
        self._mostrar_servidores(())
        self._atualizar_paginacao()
        definir_aviso(self.aviso, MENSAGEM_BUSCANDO, Tom.NEUTRO)
        tarefa = _Tarefa(
            self._geracao_busca, partial(self.client.buscar, busca), self._sinais_busca
        )
        self._pool.start(tarefa)

    def _ir_para_pagina(self, deslocamento: int) -> None:
        """Anterior/Próxima repetem a última busca feita, não o formulário editado depois."""
        if self._ultima_busca is None or self._meta is None:
            return
        self._executar(replace(self._ultima_busca, pagina=self._meta.page + deslocamento))

    def limpar(self) -> None:
        self._geracao_busca += 1
        self._ultima_busca = None
        self._meta = None
        for campo in (self.campo_nome, self.campo_cargo, self.campo_orgao):
            campo.clear()
        for combo in (self.modo, self.campo_uf, self.campo_situacao):
            combo.setCurrentIndex(0)
        self.limite.setValue(LIMITE_PADRAO)
        self.por_pagina.setCurrentIndex(POR_PAGINA_OPCOES.index(POR_PAGINA_PADRAO))
        self._marcar_erro(None)
        self._mostrar_servidores(())
        self._atualizar_paginacao()
        definir_aviso(self.aviso, MENSAGEM_INICIAL, Tom.NEUTRO)
        self.campo_nome.setFocus()

    def _busca_concluida(self, geracao: int, resultado: Resultado) -> None:
        if geracao != self._geracao_busca:
            return
        self._mostrar_servidores(resultado.servidores)
        meta = resultado.meta
        if meta is None:
            busca = self._ultima_busca
            termo = (busca.nome or busca.similar) if busca is not None else ""
            titulo = f"Nenhum vínculo com o nome “{termo}”." if termo else TITULO_VAZIO
            definir_aviso(self.aviso, f"{titulo} {DICA_VAZIO}", Tom.NEUTRO)
            return
        self._meta = meta
        partes = [f"{texto_total(meta.total, meta.total_exato)}."]
        intervalo = texto_intervalo(meta.page, meta.per_page, len(resultado.servidores), meta.total)
        if intervalo is not None:
            partes.append(intervalo)
        if meta.total_exato:
            definir_aviso(self.aviso, " ".join(partes), Tom.NEUTRO)
        else:
            definir_aviso(self.aviso, " ".join([*partes, AVISO_TOTAL_LIMITADO]), Tom.ATENCAO)
        self._atualizar_paginacao()

    def _busca_falhou(self, geracao: int, erro: ApiError) -> None:
        if geracao != self._geracao_busca:
            return
        definir_aviso(self.aviso, erro.mensagem, Tom.INFO if erro.informativo else Tom.ERRO)

    # ------------------------------------------------------------------ resultados
    def _mostrar_servidores(self, servidores: tuple[Servidor, ...]) -> None:
        self._servidores = servidores
        self.tabela.setRowCount(len(servidores))
        for linha, servidor in enumerate(servidores):
            textos = (
                servidor.nome,
                ROTULOS_SITUACAO[servidor.situacao],
                texto_ou_travessao(servidor.cargo),
                servidor.orgao,
                texto_ou_travessao(servidor.sigla_orgao),
                texto_ou_travessao(servidor.uf),
                formatar_moeda(servidor.valor),
            )
            for coluna, texto in enumerate(textos):
                celula = QTableWidgetItem(texto)
                if coluna == COLUNA_VALOR:
                    celula.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(linha, coluna, celula)
        if servidores:
            self.tabela.selectRow(0)
        self._atualizar_botao_detalhe()

    def _atualizar_paginacao(self) -> None:
        busca, meta = self._ultima_busca, self._meta
        paginada = busca is not None and not busca.similar and meta is not None
        for widget in (self.botao_anterior, self.rotulo_pagina, self.botao_proxima):
            widget.setVisible(paginada)
        if not paginada:
            return
        self.rotulo_pagina.setText(f"Página {meta.page} de {meta.total_pages}")
        self.botao_anterior.setEnabled(meta.page > 1)
        self.botao_proxima.setEnabled(meta.page < meta.total_pages)

    def _atualizar_botao_detalhe(self) -> None:
        self.botao_detalhe.setEnabled(bool(self._servidores) and self.tabela.currentRow() >= 0)

    def _marcar_erro(self, erro: ErroBusca | None) -> None:
        alvo = self._campos_por_erro.get(erro.campo) if erro is not None else None
        for campo in self._campos_por_erro.values():
            marcar_erro(campo, campo is alvo)
        if alvo is not None:
            alvo.setFocus()

    # ------------------------------------------------------------------ detalhe
    def _abrir_detalhe(self, linha: int) -> None:
        if not 0 <= linha < len(self._servidores):
            return
        servidor = self._servidores[linha]
        self._geracao_detalhe += 1
        self._dialogo = DialogoDetalhe(servidor, self)
        self._dialogo.finished.connect(self._detalhe_fechado)
        tarefa = _Tarefa(
            self._geracao_detalhe, partial(self.client.detalhar, servidor.id), self._sinais_detalhe
        )
        self._pool.start(tarefa)
        self._dialogo.open()

    def _detalhe_fechado(self) -> None:
        self._geracao_detalhe += 1
        if self._dialogo is not None:
            self._dialogo.deleteLater()
            self._dialogo = None

    def _detalhe_concluido(self, geracao: int, detalhe: Detalhe) -> None:
        if geracao == self._geracao_detalhe and self._dialogo is not None:
            self._dialogo.mostrar_detalhe(detalhe)

    def _detalhe_falhou(self, geracao: int, erro: ApiError) -> None:
        if geracao == self._geracao_detalhe and self._dialogo is not None:
            self._dialogo.mostrar_falha(erro.mensagem)

    # ------------------------------------------------------------------ configuração
    def definir_api_url(self, url: str) -> None:
        """Troca a API em uso; levanta ValueError se a URL for inválida."""
        self.client = RadarApiClient(url)
        # Respostas da API anterior que ainda chegarem são descartadas.
        self._geracao_busca += 1
        self._geracao_detalhe += 1
        self._atualizar_url()
        definir_aviso(self.aviso, "URL da API atualizada. Faça a busca de novo.", Tom.NEUTRO)

    def _alterar_url_api(self) -> None:
        url, confirmou = QInputDialog.getText(
            self, "URL da API", "Endereço base da API (termina em /api):", text=self.client.api_url
        )
        if not confirmou:
            return
        try:
            self.definir_api_url(url)
        except ValueError as erro:
            QMessageBox.warning(self, "URL da API", str(erro))
