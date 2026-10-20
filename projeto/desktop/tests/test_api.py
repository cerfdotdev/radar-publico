"""Cliente HTTP com a rede simulada: query, contrato da resposta e mensagens de erro."""

import io
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from radar_desktop.api import (
    MENSAGEM_FORMATO,
    MENSAGEM_NAO_JSON,
    MENSAGEM_TEMPO_LIMITE,
    PAGINA_PADRAO,
    POR_PAGINA_PADRAO,
    ApiError,
    Busca,
    Detalhe,
    Meta,
    RadarApiClient,
    Servidor,
    Situacao,
)

API_URL = "http://api.teste/api"

ATIVO = {
    "id": 1048213,
    "nome": "MARIA DA SILVA",
    "situacao": "ativo",
    "cargo": "ANALISTA DE FINANCAS E CONTROLE",
    "orgao": "CONTROLADORIA-GERAL DA UNIAO",
    "sigla_orgao": None,
    "uf": "DF",
    "valor": 19090.67,
}
APOSENTADO = {
    "id": 1503377,
    "nome": "MARIA DA SILVA SANTOS",
    "situacao": "aposentado",
    "cargo": None,
    "orgao": "MINISTERIO DA AGRICULTURA E PECUARIA",
    "sigla_orgao": "MAPA",
    "uf": None,
    "valor": None,
}
META = {"total": 2, "total_exato": True, "page": 1, "per_page": 20, "total_pages": 1}
CAMPOS_DETALHE = {
    "codigo_carreira": None,
    "tipo_aposentadoria": "VOLUNTARIA",
    "fundamento_legal": "CF 40 III C",
    "portaria": None,
    "data_aposentadoria": "1990-07-02",
    "forma_ingresso": "ADMISSAO SEM CONCURSO PUBLICO",
    "data_ingresso": "1959-10-01",
    "referencia": "2026-05",
}


def resposta(corpo: object) -> MagicMock:
    """Resposta 200 de urlopen; bytes vão como estão, o resto vira JSON."""
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.read.return_value = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
    return mock


def erro_http(status: int, corpo: object = None, headers: dict | None = None) -> HTTPError:
    if corpo is None:
        dados = b""
    elif isinstance(corpo, bytes):
        dados = corpo
    else:
        dados = json.dumps(corpo).encode()
    return HTTPError(f"{API_URL}/servidores", status, "erro", headers or {}, io.BytesIO(dados))


def erro_contrato(codigo: str, mensagem: str = "Mensagem da API.") -> dict:
    return {"error": {"code": codigo, "message": mensagem}}


@pytest.fixture
def urlopen():
    with patch("radar_desktop.api.urlopen") as mock:
        yield mock


def falha_de(urlopen: MagicMock, efeito: object, busca: Busca | None = None) -> ApiError:
    urlopen.side_effect = efeito
    with pytest.raises(ApiError) as capturado:
        RadarApiClient(API_URL).buscar(busca or Busca(nome="Maria"))
    return capturado.value


# --- Query ---


def test_nome_exato_com_filtros_e_situacao():
    busca = Busca(
        nome="Maria da Silva", cargo="professor", orgao="INSS", uf="DF", situacao=Situacao.ATIVO
    )
    assert busca.parametros() == [
        ("nome", "Maria da Silva"),
        ("cargo", "professor"),
        ("orgao", "INSS"),
        ("uf", "DF"),
        ("situacao", "ativo"),
    ]


def test_situacao_todos_e_paginacao_padrao_nao_entram():
    busca = Busca(cargo="professor", pagina=PAGINA_PADRAO, por_pagina=POR_PAGINA_PADRAO)
    assert busca.parametros() == [("cargo", "professor")]


def test_paginacao_diferente_do_padrao():
    assert Busca(nome="Maria", pagina=2, por_pagina=50).parametros() == [
        ("nome", "Maria"),
        ("page", "2"),
        ("per_page", "50"),
    ]


def test_similar_envia_limit_e_nao_pagina():
    busca = Busca(similar="%MARIA%SILVA%", limite=50, pagina=2, por_pagina=50)
    assert busca.parametros() == [("similar", "%MARIA%SILVA%"), ("limit", "50")]


def test_limit_nunca_vai_sem_similar():
    assert all(nome != "limit" for nome, _ in Busca(nome="Maria", limite=10).parametros())


def test_url_da_busca_e_cabecalhos(urlopen):
    urlopen.return_value = resposta({"data": [ATIVO], "meta": META})
    RadarApiClient(f"{API_URL}/").buscar(Busca(similar="%MARIA SILVA%", limite=10))

    requisicao = urlopen.call_args.args[0]
    assert requisicao.full_url == f"{API_URL}/servidores?similar=%25MARIA+SILVA%25&limit=10"
    assert requisicao.get_header("Accept") == "application/json"
    assert urlopen.call_args.kwargs["timeout"] == RadarApiClient(API_URL).tempo_limite_s


def test_url_invalida_e_recusada():
    with pytest.raises(ValueError):
        RadarApiClient("file:///etc/passwd")


# --- Resposta 200 ---


def test_busca_le_o_contrato_com_campos_nulos(urlopen):
    urlopen.return_value = resposta({"data": [ATIVO, APOSENTADO], "meta": META})
    resultado = RadarApiClient(API_URL).buscar(Busca(nome="Maria da Silva"))

    assert resultado.meta == Meta(total=2, total_exato=True, page=1, per_page=20, total_pages=1)
    ativo, aposentado = resultado.servidores
    assert ativo == Servidor(**{**ATIVO, "situacao": Situacao.ATIVO})
    assert aposentado.uf is None and aposentado.valor is None and aposentado.cargo is None
    assert aposentado.situacao is Situacao.APOSENTADO


def test_campos_a_mais_sao_ignorados(urlopen):
    item = {**ATIVO, "similaridade": 0.82}
    urlopen.return_value = resposta({"data": [item], "meta": {**META, "total": 1}})
    assert RadarApiClient(API_URL).buscar(Busca(similar="MARIA")).servidores[0].id == ATIVO["id"]


def test_valor_inteiro_vira_float(urlopen):
    urlopen.return_value = resposta({"data": [{**ATIVO, "valor": 5000}], "meta": META})
    assert RadarApiClient(API_URL).buscar(Busca(nome="Maria")).servidores[0].valor == 5000.0


def test_nao_encontrado_e_estado_vazio(urlopen):
    urlopen.side_effect = erro_http(404, erro_contrato("NAO_ENCONTRADO"))
    resultado = RadarApiClient(API_URL).buscar(Busca(nome="Fulano"))
    assert resultado.servidores == () and resultado.meta is None


def test_lista_vazia_tambem_e_estado_vazio(urlopen):
    urlopen.return_value = resposta({"data": [], "meta": {**META, "total": 0}})
    assert RadarApiClient(API_URL).buscar(Busca(nome="Fulano")).meta is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"data": "não é lista", "meta": META},
        {"data": [ATIVO]},
        {"data": [ATIVO], "meta": {**META, "total_exato": "sim"}},
        {"data": [ATIVO], "meta": {**META, "page": -1}},
        {"data": [ATIVO], "meta": {**META, "total_pages": "1"}},
        {"data": [{**ATIVO, "situacao": "pensionista"}], "meta": META},
        {"data": [{**ATIVO, "valor": "19090,67"}], "meta": META},
        {"data": [{**ATIVO, "id": True}], "meta": META},
        {"data": [{key: v for key, v in ATIVO.items() if key != "nome"}], "meta": META},
        {"data": [ATIVO, "texto"], "meta": META},
        [ATIVO],
    ],
)
def test_resposta_fora_do_contrato(urlopen, corpo):
    assert falha_de(urlopen, [resposta(corpo)]).mensagem == MENSAGEM_FORMATO


def test_valor_nao_finito_esta_fora_do_contrato(urlopen):
    corpo = json.dumps({"data": [ATIVO], "meta": META}).replace("19090.67", "NaN").encode()
    assert falha_de(urlopen, [resposta(corpo)]).mensagem == MENSAGEM_FORMATO


def test_200_sem_json(urlopen):
    assert falha_de(urlopen, [resposta(b"<html>proxy</html>")]).mensagem == MENSAGEM_NAO_JSON


# --- Erros do contrato ---


@pytest.mark.parametrize(
    ("status", "codigo", "trecho"),
    [
        (400, "PARAMETRO_DESCONHECIDO", "não reconheceu um parâmetro"),
        (400, "PARAMETRO_INVALIDO", "A API recusou a busca: Mensagem da API."),
        (400, "FILTRO_OBRIGATORIO", "Informe um nome ou ao menos um filtro"),
        (400, "UF_INVALIDA", "UF inválida"),
        (404, "CARGO_NAO_ENCONTRADO", "Nenhum cargo corresponde"),
        (404, "ORGAO_NAO_ENCONTRADO", "Nenhum órgão corresponde"),
        (404, "PAGINA_INEXISTENTE", "Esta página não existe"),
        (404, "ROTA_INEXISTENTE", "termina em /api"),
        (405, "METODO_NAO_PERMITIDO", "tipo de requisição"),
        (504, "TEMPO_ESGOTADO", "demorou demais e foi interrompida"),
        (502, "SERVIDOR_INDISPONIVEL", "fora do ar"),
        (500, "ERRO_INTERNO", "Algo deu errado na API"),
    ],
)
def test_cada_codigo_tem_mensagem_propria(urlopen, status, codigo, trecho):
    erro = falha_de(urlopen, erro_http(status, erro_contrato(codigo)))
    assert trecho in erro.mensagem
    assert (erro.status, erro.codigo, erro.informativo) == (status, codigo, False)


@pytest.mark.parametrize(
    ("status", "codigo", "trecho"),
    [(429, "MUITAS_REQUISICOES", "Muitas buscas"), (503, "SERVIDOR_OCUPADO", "ocupado")],
)
def test_limites_de_uso_mostram_o_retry_after(urlopen, status, codigo, trecho):
    efeito = erro_http(status, erro_contrato(codigo), {"Retry-After": "7"})
    erro = falha_de(urlopen, efeito)
    assert trecho in erro.mensagem
    assert erro.mensagem.endswith("Tente de novo em 7 segundos.")
    assert erro.retry_after == 7 and erro.informativo


def test_retry_after_de_um_segundo_no_singular(urlopen):
    efeito = erro_http(503, erro_contrato("SERVIDOR_OCUPADO"), {"Retry-After": "1"})
    assert falha_de(urlopen, efeito).mensagem.endswith("Tente de novo em 1 segundo.")


def test_retry_after_em_formato_de_data_e_ignorado(urlopen):
    efeito = erro_http(
        429, erro_contrato("MUITAS_REQUISICOES"), {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
    )
    erro = falha_de(urlopen, efeito)
    assert erro.retry_after is None
    assert erro.mensagem.endswith("Tente de novo em instantes.")


@pytest.mark.parametrize(
    ("status", "codigo"),
    [(429, "MUITAS_REQUISICOES"), (500, "ERRO_INTERNO"), (502, "SERVIDOR_INDISPONIVEL"),
     (503, "SERVIDOR_OCUPADO"), (504, "TEMPO_ESGOTADO")],
)  # fmt: skip
def test_erro_sem_json_usa_o_codigo_do_status(urlopen, status, codigo):
    assert falha_de(urlopen, erro_http(status, b"<html>nginx</html>")).codigo == codigo


def test_codigo_desconhecido_usa_a_mensagem_da_api(urlopen):
    erro = falha_de(urlopen, erro_http(418, erro_contrato("NOVO_CODIGO", "Algo novo.")))
    assert erro.mensagem == "Algo novo."


def test_status_desconhecido_sem_corpo(urlopen):
    assert falha_de(urlopen, erro_http(418)).mensagem == "A API respondeu com erro (HTTP 418)."


# --- Rede ---


@pytest.mark.parametrize("efeito", [TimeoutError(), URLError(TimeoutError())])
def test_tempo_limite(urlopen, efeito):
    assert falha_de(urlopen, efeito).mensagem == MENSAGEM_TEMPO_LIMITE


@pytest.mark.parametrize("efeito", [URLError(ConnectionRefusedError()), ConnectionResetError()])
def test_sem_conexao(urlopen, efeito):
    mensagem = falha_de(urlopen, efeito).mensagem
    assert mensagem.startswith(f"Não foi possível conectar à API em {API_URL}.")


# --- Detalhe ---


def test_detalhe(urlopen):
    urlopen.return_value = resposta({"data": {**APOSENTADO, **CAMPOS_DETALHE}})
    detalhe = RadarApiClient(API_URL).detalhar(APOSENTADO["id"])

    assert urlopen.call_args.args[0].full_url == f"{API_URL}/servidores/{APOSENTADO['id']}"
    assert isinstance(detalhe, Detalhe)
    assert detalhe.tipo_aposentadoria == "VOLUNTARIA" and detalhe.portaria is None


def test_detalhe_fora_do_contrato(urlopen):
    urlopen.return_value = resposta({"data": {**APOSENTADO, "referencia": 202605}})
    with pytest.raises(ApiError) as capturado:
        RadarApiClient(API_URL).detalhar(APOSENTADO["id"])
    assert capturado.value.mensagem == MENSAGEM_FORMATO


def test_detalhe_sem_a_rota_na_api(urlopen):
    urlopen.side_effect = erro_http(404, erro_contrato("ROTA_INEXISTENTE"))
    with pytest.raises(ApiError) as capturado:
        RadarApiClient(API_URL).detalhar(1)
    assert capturado.value.codigo == "ROTA_INEXISTENTE"
