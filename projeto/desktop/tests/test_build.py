"""build.py: modo onedir (LGPL-3.0) e licenças dentro do executável.

Pulados sem as dependências de build (requirements-build.txt), como no job desktop do CI.
"""

import os

import pytest

pytest.importorskip("PyInstaller")

import build  # noqa: E402


def test_build_e_onedir_e_nunca_onefile(tmp_path):
    argumentos = build.argumentos_pyinstaller(tmp_path / "LICENSE.txt")
    assert "--onedir" in argumentos
    assert "--onefile" not in argumentos
    assert argumentos[argumentos.index("--name") + 1] == build.NOME_EXECUTAVEL


def test_licencas_vao_para_dentro_do_executavel(tmp_path):
    licenca_python = tmp_path / "LICENSE.txt"
    argumentos = build.argumentos_pyinstaller(licenca_python)
    assert f"{build.LICENCAS}{os.pathsep}{build.LICENCAS_DESTINO}" in argumentos
    assert f"{licenca_python}{os.pathsep}{build.LICENCA_PYTHON_DESTINO}" in argumentos


def test_textos_de_licenca_versionados():
    nomes = {arquivo.name for arquivo in build.LICENCAS.iterdir()}
    assert {"AVISO.txt", "LGPL-3.0.txt", "GPL-3.0.txt"} <= nomes


def test_licenca_do_python_encontrada():
    assert build.licenca_do_python().is_file()
