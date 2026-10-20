"""Verificação rápida do app (--verificar): abre a janela fora da tela e sai.

Serve para conferir que um executável gerado pelo build.py abre de verdade: carrega as
bibliotecas do Qt e o plugin de plataforma, monta a janela e consulta GET <api>/health.
A API fora do ar só é informada: a verificação é do executável, não do backend.
"""

import json
import os
import sys
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__
from .api import USER_AGENT, RadarApiClient
from .app import NOME_APP, criar_aplicacao
from .window import MainWindow

VARIAVEL_PLATAFORMA = "QT_QPA_PLATFORM"
# Plugin do Qt que desenha em memória: a verificação não abre nada na tela.
PLATAFORMA_SEM_TELA = "offscreen"
# Bem menor que o das buscas (TEMPO_LIMITE_S): a API fora do ar não pode travar a verificação.
TEMPO_LIMITE_SAUDE_S = 5
CAMINHO_SAUDE = "health"
STATUS_SAUDAVEL = "ok"
CODIGO_SUCESSO = 0
CODIGO_FALHA = 1


def consultar_saude(api_url: str, tempo_limite_s: float = TEMPO_LIMITE_SAUDE_S) -> str | None:
    """None se GET <api>/health respondeu {"status": "ok"}; senão, o motivo."""
    requisicao = Request(
        f"{api_url}/{CAMINHO_SAUDE}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        # Esquema limitado a http/https: a URL já passou por validar_url.
        with urlopen(requisicao, timeout=tempo_limite_s) as resposta:  # nosec B310
            dados = json.loads(resposta.read().decode("utf-8"))
    except HTTPError as erro:
        erro.close()
        return f"respondeu HTTP {erro.code}"
    except (OSError, HTTPException) as erro:
        # URLError guarda a causa em reason ("Connection refused", "timed out"...).
        return f"sem conexão: {getattr(erro, 'reason', erro)}"
    except ValueError:
        return "a resposta não é JSON"
    if not isinstance(dados, dict) or dados.get("status") != STATUS_SAUDAVEL:
        return "resposta fora do formato de docs/api.md"
    return None


def verificar(api_url: str) -> int:
    """Abre e fecha a janela sem mostrar na tela; devolve o código de saída do processo."""
    os.environ.setdefault(VARIAVEL_PLATAFORMA, PLATAFORMA_SEM_TELA)
    try:
        app = criar_aplicacao()
        janela = MainWindow(RadarApiClient(api_url))
        janela.show()
        app.processEvents()
        aberta = janela.isVisible()
        janela.close()
    except Exception as erro:
        # No executável sem console, uma exceção solta viraria uma caixa de diálogo
        # esperando clique, e quem chamou (o CI) ficaria preso.
        print(f"{NOME_APP}: falha ao abrir a janela: {erro}", file=sys.stderr)
        return CODIGO_FALHA
    if not aberta:
        print(f"{NOME_APP}: a janela não ficou visível.", file=sys.stderr)
        return CODIGO_FALHA

    print(f"{NOME_APP} {__version__}: janela ok (plataforma {app.platformName()}).")
    motivo = consultar_saude(api_url)
    if motivo is None:
        print(f"API em {api_url}: ok.")
    else:
        print(f"API em {api_url}: indisponível ({motivo}).")
    return CODIGO_SUCESSO
