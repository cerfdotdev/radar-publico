from __future__ import annotations

import unittest

from radar_desktop.api import Busca
from radar_desktop.validacao import UFS, normalizar_nome, validar_busca


class ValidacaoTests(unittest.TestCase):
    def test_exige_algum_filtro(self) -> None:
        erro = validar_busca(Busca())
        self.assertEqual(erro.campo if erro else None, "termo")

    def test_nome_exato_com_filtros_combinados(self) -> None:
        self.assertIsNone(validar_busca(Busca(nome="José D'Ávila", cargo="professor", uf="DF")))

    def test_nome_parecido_precisa_de_tres_letras(self) -> None:
        erro = validar_busca(Busca(similar="%%%"))
        self.assertEqual(erro.campo if erro else None, "termo")

    def test_nome_parecido_aceita_curinga(self) -> None:
        self.assertIsNone(validar_busca(Busca(similar="%MARIA%SILVA%", limite=50)))

    def test_limite_fora_da_faixa(self) -> None:
        erro = validar_busca(Busca(similar="MARIA", limite=101))
        self.assertEqual(erro.campo if erro else None, "limite")

    def test_uf_invalida(self) -> None:
        erro = validar_busca(Busca(uf="XX"))
        self.assertEqual(erro.campo if erro else None, "uf")

    def test_normalizacao(self) -> None:
        self.assertEqual(normalizar_nome("  José   D'Ávila "), "JOSE D'AVILA")
        self.assertIn("DF", UFS)


if __name__ == "__main__":
    unittest.main()
