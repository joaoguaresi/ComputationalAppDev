"""Testes do config.json seguro para a bancada (0 a 12 V e ±30 A).

Usam uma pasta temporária no lugar de data/: o config.json de verdade não é tocado.
"""

import json
import logging
import os
import tempfile
import unittest

from models.config_manager import ConfigManager

logging.getLogger("smartgrid").addHandler(logging.NullHandler())


class TestConfigSeguro(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._originais = (ConfigManager.PASTA_DATA, ConfigManager.CAMINHO, ConfigManager._dados)
        ConfigManager.PASTA_DATA = self._pasta.name
        ConfigManager.CAMINHO = os.path.join(self._pasta.name, "config.json")
        ConfigManager._dados = None

    def tearDown(self):
        ConfigManager.PASTA_DATA, ConfigManager.CAMINHO, ConfigManager._dados = self._originais
        self._pasta.cleanup()

    def _gravar(self, dados):
        with open(ConfigManager.CAMINHO, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo)

    def _ler(self):
        with open(ConfigManager.CAMINHO, encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def test_arquivo_excluido_e_recriado_com_os_padroes(self):
        ConfigManager.carregar()
        self.assertEqual(self._ler(), ConfigManager.DEFAULTS)
        self.assertEqual(ConfigManager.get("baud_rate"), 115200)

    def test_padroes_cabem_na_bancada(self):
        self.assertLessEqual(ConfigManager.DEFAULTS["tensao_desarme"], ConfigManager.TENSAO_MAXIMA_V)
        self.assertLessEqual(ConfigManager.DEFAULTS["corrente_max"], ConfigManager.CORRENTE_MAXIMA_A)
        self.assertAlmostEqual(ConfigManager.DEFAULTS["fator_tensao"] * 1023, 12.0)

    def test_limite_acima_da_bancada_volta_ao_padrao_e_o_arquivo_e_corrigido(self):
        self._gravar({"tensao_desarme": 242.0, "corrente_max": 45.0})
        ConfigManager.carregar()
        self.assertEqual(ConfigManager.get("tensao_desarme"), 11.5)
        self.assertEqual(ConfigManager.get("corrente_max"), 25.0)
        self.assertEqual(self._ler()["tensao_desarme"], 11.5)

    def test_taxa_que_a_placa_nao_aceita_volta_ao_padrao(self):
        for taxa in (57600, "115200", True, 115200.0):
            with self.subTest(taxa=taxa):
                self._gravar({"baud_rate": taxa})
                ConfigManager.carregar()
                self.assertEqual(ConfigManager.get("baud_rate"), 115200)

    def test_as_quatro_taxas_sao_mantidas(self):
        for taxa in (9600, 19200, 38400, 115200):
            with self.subTest(taxa=taxa):
                self._gravar({"baud_rate": taxa})
                ConfigManager.carregar()
                self.assertEqual(ConfigManager.get("baud_rate"), taxa)

    def test_tipo_errado_volta_ao_padrao(self):
        self._gravar({"tensao_desarme": "abc", "zero_corrente_adc": -3, "porta_com": 3})
        ConfigManager.carregar()
        self.assertEqual(ConfigManager.get("tensao_desarme"), 11.5)
        self.assertEqual(ConfigManager.get("zero_corrente_adc"), 512.0)
        self.assertEqual(ConfigManager.get("porta_com"), "COM1")

    def test_valores_validos_sao_mantidos_e_chaves_novas_acrescentadas(self):
        self._gravar({"porta_com": "COM5", "tensao_desarme": 10.0, "corrente_max": 6})
        ConfigManager.carregar()
        self.assertEqual(ConfigManager.get("porta_com"), "COM5")
        self.assertEqual(ConfigManager.get("tensao_desarme"), 10.0)
        self.assertEqual(ConfigManager.get("corrente_max"), 6)
        self.assertIn("fator_tensao", self._ler())


if __name__ == "__main__":
    unittest.main()
