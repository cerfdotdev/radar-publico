"""Gera o executável do app desktop com o PyInstaller: python build.py

Saída em dist/RadarPublico/ (modo onedir): o executável e, em _internal/, o Python, o
PySide6 e as bibliotecas do Qt como arquivos separados. É o que a LGPL-3.0 do Qt for
Python pede: quem recebe o app consegue trocar essas bibliotecas por outra versão
compatível. Por isso o build nunca usa --onefile. Os avisos e os textos de licença vão
junto, em _internal/LICENCAS/.

Requer as dependências do app e as de build (README, "Executável").
"""

import os
import sys
import sysconfig
from pathlib import Path

import PyInstaller.__main__

RAIZ = Path(__file__).resolve().parent
NOME_EXECUTAVEL = "RadarPublico"
ENTRADA = RAIZ / "main.py"
PASTA_DIST = RAIZ / "dist"
PASTA_BUILD = RAIZ / "build"
# Avisos e textos de licença versionados: o wheel do PySide6 não traz nenhum.
LICENCAS = RAIZ / "licencas"
LICENCAS_DESTINO = "LICENCAS"
# Licença do Python embutido: fica na stdlib (Linux, macOS) ou na raiz da instalação (Windows).
LICENCA_PYTHON = "LICENSE.txt"
LICENCA_PYTHON_DESTINO = f"{LICENCAS_DESTINO}/python"


def licenca_do_python() -> Path:
    candidatos = (
        Path(sysconfig.get_path("stdlib")) / LICENCA_PYTHON,
        Path(sys.base_prefix) / LICENCA_PYTHON,
    )
    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    raise FileNotFoundError(
        f"{LICENCA_PYTHON} do Python não encontrado em: {', '.join(map(str, candidatos))}"
    )


def incluir(origem: Path, destino: str) -> list[str]:
    """--add-data no formato ORIGEM<separador>DESTINO, com o separador do sistema."""
    return ["--add-data", f"{origem}{os.pathsep}{destino}"]


def argumentos_pyinstaller(licenca_python: Path) -> list[str]:
    """Opções do PyInstaller; o .spec gerado fica em build/, fora do Git."""
    return [
        str(ENTRADA),
        "--name",
        NOME_EXECUTAVEL,
        # Bibliotecas do Qt como arquivos substituíveis (LGPL-3.0). Nunca --onefile.
        "--onedir",
        # Sem janela de console no Windows; no macOS gera também o pacote .app.
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(PASTA_DIST),
        "--workpath",
        str(PASTA_BUILD),
        "--specpath",
        str(PASTA_BUILD),
        *incluir(LICENCAS, LICENCAS_DESTINO),
        *incluir(licenca_python, LICENCA_PYTHON_DESTINO),
    ]


def main() -> int:
    PyInstaller.__main__.run(argumentos_pyinstaller(licenca_do_python()))
    print(f"Executável gerado em {PASTA_DIST / NOME_EXECUTAVEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
