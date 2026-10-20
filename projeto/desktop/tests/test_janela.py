"""Janela principal com um cliente falso: teclado, estados, respostas atrasadas e detalhe.

Pulados se o Qt não puder ser carregado (ex.: sem as bibliotecas gráficas do sistema).
"""

import threading
import time
from dataclasses import replace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from PySide6.QtCore import QCoreApplication, Qt, QThreadPool  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from radar_desktop.api import (  # noqa: E402
    ApiError,
    Busca,
    Detalhe,
    Meta,
    Resultado,
    Servidor,
    Situacao,
)
from radar_desktop.app import criar_aplicacao  # noqa: E402
from radar_desktop.detalhe import INDISPONIVEL  # noqa: E402
from radar_desktop.window import MODO_SIMILAR, MainWindow  # noqa: E402

# Tempo máximo esperando as tarefas do QThreadPool num teste.
ESPERA_MS = 5_000
ESPERA_S = ESPERA_MS / 1000
INTERVALO_MS = 10

ATIVO = Servidor(
    id=1,
    nome="MARIA DA SILVA",
    situacao=Situacao.ATIVO,
    cargo=None,
    orgao="CONTROLADORIA-GERAL DA UNIAO",
    sigla_orgao=None,
    uf="DF",
    valor=19090.67,
)
APOSENTADO = replace(ATIVO, id=2, nome="JOSE SANTOS", situacao=Situacao.APOSENTADO, uf=None)


def pagina(*servidores: Servidor, page: int = 1, total_pages: int = 1) -> Resultado:
    meta = Meta(total=len(servidores) * total_pages, total_exato=True, page=page,
                per_page=20, total_pages=total_pages)  # fmt: skip
    return Resultado(servidores=servidores, meta=meta)


class ClienteFalso:
    """Responde na ordem da lista; uma exceção é levantada e um callable é chamado."""

    api_url = "http://api.teste/api"

    def __init__(self, *respostas: object, detalhe: object = None) -> None:
        self.respostas = list(respostas)
        self.detalhe = detalhe
        self.buscas: list[Busca] = []

    @staticmethod
    def _responder(resposta: object) -> object:
        if callable(resposta):
            resposta = resposta()
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def buscar(self, busca: Busca) -> object:
        self.buscas.append(busca)
        return self._responder(self.respostas.pop(0))

    def detalhar(self, servidor_id: int) -> object:
        return self._responder(self.detalhe)


def esperar_tarefas() -> None:
    assert QThreadPool.globalInstance().waitForDone(ESPERA_MS)
    QCoreApplication.processEvents()


def esperar_ate(condicao) -> None:
    prazo = time.monotonic() + ESPERA_S
    while not condicao():
        assert time.monotonic() < prazo, "a tela não chegou ao estado esperado"
        QTest.qWait(INTERVALO_MS)


@pytest.fixture(scope="module")
def app():
    return criar_aplicacao([])


@pytest.fixture
def abrir(app):
    janelas = []

    def abrir_janela(cliente: ClienteFalso) -> MainWindow:
        janela = MainWindow(cliente)
        janela.show()
        janela.activateWindow()
        QTest.qWaitForWindowActive(janela)
        janelas.append(janela)
        return janela

    yield abrir_janela
    esperar_tarefas()
    for janela in janelas:
        janela.close()


def test_enter_no_campo_de_nome_busca(abrir):
    cliente = ClienteFalso(pagina(ATIVO))
    janela = abrir(cliente)
    janela.campo_nome.setText("  Maria   da Silva ")
    janela.campo_nome.setFocus()

    QTest.keyClick(janela.campo_nome, Qt.Key.Key_Return)
    esperar_tarefas()

    assert cliente.buscas == [Busca(nome="Maria da Silva")]
    assert janela.tabela.rowCount() == 1
    assert janela.tabela.item(0, 0).text() == "MARIA DA SILVA"
    assert janela.aviso.text() == "1 resultado encontrado."


def test_enter_numa_lista_do_formulario_busca(abrir):
    cliente = ClienteFalso(pagina(ATIVO))
    janela = abrir(cliente)
    janela.campo_uf.setCurrentIndex(janela.campo_uf.findData("DF"))
    janela.campo_uf.setFocus()

    QTest.keyClick(janela.campo_uf, Qt.Key.Key_Enter)
    esperar_tarefas()

    assert cliente.buscas == [Busca(uf="DF")]


def test_campos_nulos_aparecem_como_travessao(abrir):
    janela = abrir(ClienteFalso(pagina(APOSENTADO)))
    janela.campo_nome.setText("Jose Santos")
    janela.buscar()
    esperar_tarefas()

    textos = [janela.tabela.item(0, coluna).text() for coluna in range(janela.tabela.columnCount())]
    assert textos == ["JOSE SANTOS", "Aposentado", "—", "CONTROLADORIA-GERAL DA UNIAO", "—", "—",
                      "R$ 19.090,67"]  # fmt: skip


def test_validacao_local_nao_chama_a_api(abrir):
    cliente = ClienteFalso()
    janela = abrir(cliente)
    janela.campo_uf.setCurrentIndex(janela.campo_uf.findData("DF"))
    janela.campo_situacao.setCurrentIndex(janela.campo_situacao.findData(Situacao.APOSENTADO))

    janela.buscar()

    assert cliente.buscas == []
    assert janela.aviso.property("tom") == "erro"
    assert "Aposentados não têm UF" in janela.aviso.text()
    assert janela.campo_uf.property("erro") == "true"


def test_resposta_atrasada_de_busca_antiga_e_descartada(abrir):
    liberar = threading.Event()

    def busca_lenta() -> Resultado:
        liberar.wait(ESPERA_S)
        return pagina(APOSENTADO)

    cliente = ClienteFalso(busca_lenta, pagina(ATIVO))
    janela = abrir(cliente)
    janela.campo_nome.setText("Jose Santos")
    janela.buscar()
    janela.campo_nome.setText("Maria da Silva")
    janela.buscar()
    # A busca nova responde primeiro; só depois a antiga termina.
    esperar_ate(lambda: janela.tabela.rowCount() == 1)
    liberar.set()
    esperar_tarefas()

    assert janela.tabela.item(0, 0).text() == "MARIA DA SILVA"
    assert janela.aviso.text() == "1 resultado encontrado."


def test_limpar_descarta_a_busca_em_andamento(abrir):
    liberar = threading.Event()

    def busca_lenta() -> Resultado:
        liberar.wait(ESPERA_S)
        return pagina(ATIVO)

    janela = abrir(ClienteFalso(busca_lenta))
    janela.campo_nome.setText("Maria")
    janela.buscar()
    janela.limpar()
    liberar.set()
    esperar_tarefas()

    assert janela.tabela.rowCount() == 0
    assert janela.aviso.property("tom") == "neutro"


def test_estado_vazio_nao_e_erro(abrir):
    janela = abrir(ClienteFalso(Resultado(servidores=(), meta=None)))
    janela.campo_nome.setText("Fulano de Tal")
    janela.buscar()
    esperar_tarefas()

    assert janela.aviso.property("tom") == "neutro"
    assert janela.aviso.text().startswith("Nenhum vínculo com o nome “Fulano de Tal”.")


@pytest.mark.parametrize(("informativo", "tom"), [(True, "info"), (False, "erro")])
def test_erro_da_api_vira_aviso(abrir, informativo, tom):
    erro = ApiError("Mensagem para a tela.", informativo=informativo)
    janela = abrir(ClienteFalso(erro))
    janela.campo_nome.setText("Maria")
    janela.buscar()
    esperar_tarefas()

    assert janela.aviso.text() == "Mensagem para a tela."
    assert janela.aviso.property("tom") == tom


def test_excecao_inesperada_nao_trava_a_tela(abrir):
    janela = abrir(ClienteFalso(RuntimeError("bug")))
    janela.campo_nome.setText("Maria")
    janela.buscar()
    esperar_tarefas()

    assert janela.aviso.property("tom") == "erro"
    assert "erro inesperado" in janela.aviso.text()


def test_proxima_pagina_repete_a_ultima_busca(abrir):
    cliente = ClienteFalso(pagina(ATIVO, total_pages=3), pagina(APOSENTADO, page=2, total_pages=3))
    janela = abrir(cliente)
    janela.campo_cargo.setText("analista")
    janela.buscar()
    esperar_tarefas()
    assert not janela.botao_anterior.isEnabled() and janela.botao_proxima.isEnabled()

    janela.campo_cargo.setText("editado depois")
    janela.botao_proxima.click()
    esperar_tarefas()

    assert cliente.buscas[1] == replace(cliente.buscas[0], pagina=2)
    assert janela.rotulo_pagina.text() == "Página 2 de 3"
    assert janela.botao_anterior.isEnabled()


def test_nome_parecido_nao_tem_paginacao(abrir):
    cliente = ClienteFalso(pagina(ATIVO))
    janela = abrir(cliente)
    janela.modo.setCurrentIndex(janela.modo.findData(MODO_SIMILAR))
    janela.campo_nome.setText("%MARIA%")
    janela.limite.setValue(10)
    janela.buscar()
    esperar_tarefas()

    assert cliente.buscas == [Busca(similar="%MARIA%", limite=10)]
    assert not janela.por_pagina.isEnabled()
    assert janela.botao_proxima.isHidden()


def test_nome_parecido_combina_com_os_filtros(abrir):
    cliente = ClienteFalso(pagina(ATIVO))
    janela = abrir(cliente)
    janela.modo.setCurrentIndex(janela.modo.findData(MODO_SIMILAR))
    janela.campo_nome.setText("%MARIA%")
    janela.campo_cargo.setText("professor")
    janela.campo_uf.setCurrentIndex(janela.campo_uf.findData("RJ"))
    janela.campo_situacao.setCurrentIndex(janela.campo_situacao.findData(Situacao.ATIVO))
    janela.buscar()
    esperar_tarefas()

    assert all(campo.isEnabled() for campo in (janela.campo_cargo, janela.campo_orgao))
    assert cliente.buscas == [
        Busca(similar="%MARIA%", cargo="professor", uf="RJ", situacao=Situacao.ATIVO)
    ]


def test_detalhe_completa_a_ficha(abrir):
    detalhe = Detalhe(
        **{**vars(APOSENTADO)},
        codigo_carreira=None,
        tipo_aposentadoria="VOLUNTARIA",
        fundamento_legal="CF 40 III C",
        portaria=None,
        data_aposentadoria="1990-07-02",
        forma_ingresso=None,
        data_ingresso="1959-10-01",
        referencia="2026-05",
    )
    janela = abrir(ClienteFalso(pagina(APOSENTADO), detalhe=detalhe))
    janela.campo_nome.setText("Jose Santos")
    janela.buscar()
    esperar_tarefas()

    janela.botao_detalhe.click()
    esperar_tarefas()

    dialogo = janela._dialogo
    assert dialogo is not None and dialogo.aviso.isHidden()
    assert dialogo._valores["data_aposentadoria"].text() == "02/07/1990"
    assert dialogo._valores["uf"].text().startswith("Não informada")
    assert dialogo._valores["portaria"].text() == "—"
    dialogo.reject()


def test_detalhe_indisponivel_mantem_os_dados_da_lista(abrir):
    falha = ApiError("A API não tem este endereço.", codigo="ROTA_INEXISTENTE")
    janela = abrir(ClienteFalso(pagina(ATIVO), detalhe=falha))
    janela.campo_nome.setText("Maria da Silva")
    janela.buscar()
    esperar_tarefas()

    janela.tabela.setFocus()
    QTest.keyClick(janela.tabela, Qt.Key.Key_Return)
    esperar_tarefas()

    dialogo = janela._dialogo
    assert dialogo is not None
    assert "A API não tem este endereço." in dialogo.aviso.text()
    assert dialogo._valores["valor"].text() == "R$ 19.090,67"
    assert dialogo._valores["codigo_carreira"].text() == INDISPONIVEL
    dialogo.reject()
