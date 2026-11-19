"""Testes do Bloco 4 com o dashboard inteiro: gráfico em tempo real e disjuntor pelo STATUS_RELE.

Montam o MainWindowController de verdade (thread serial e thread do banco) em modo
offscreen, com a PlacaSimulada no lugar do Arduino e um banco temporário no lugar de
data/smartgrid.db. Nada de verdade é tocado: nem a placa, nem o banco, nem o config.json.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import logging
import tempfile
import time
import unittest

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from controllers.main_window_controller import MainWindowController
from database.connection import Database
from models.config_manager import ConfigManager
from models.dispositivo import Dispositivo
from models.dispositivo_repository import DispositivoRepository
from models.evento_historico import EventoHistorico
from models.evento_repository import EventoRepository
from testes.placa_simulada import PlacaSimulada

logging.getLogger("smartgrid").addHandler(logging.NullHandler())

app = QApplication.instance() or QApplication([])
TEM_WIDGETS = isinstance(app, QApplication)

PORTA = "COM9"


def esperar(condicao, timeout_s=4.0) -> bool:
    """Processa os eventos do Qt (é assim que os sinais das threads chegam) até a condição valer."""
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        app.processEvents()
        if condicao():
            return True
        time.sleep(0.005)
    app.processEvents()
    return condicao()


def status_no_banco():
    return DispositivoRepository.buscar_por_tag(Dispositivo.TAG_DISJUNTOR_PRINCIPAL).status


@unittest.skipUnless(TEM_WIDGETS, "outro teste já criou uma QCoreApplication sem widgets")
class TestDashboardComPlaca(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._originais = (Database.PASTA_DATA, Database.CAMINHO, ConfigManager._dados)
        Database.PASTA_DATA = self._pasta.name
        Database.CAMINHO = os.path.join(self._pasta.name, "smartgrid.db")
        ConfigManager._dados = dict(ConfigManager.DEFAULTS)
        # Potenciômetro em A1: o zero fica fixo em 512, sem calibrar.
        ConfigManager._dados["calibrar_zero_corrente"] = False
        self.assertTrue(Database.init_db())

        self._pergunta_original = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)

        self.placa = PlacaSimulada(a0=900, a1=700)
        self.janela = QMainWindow()
        self.dashboard = MainWindowController(self.janela)
        worker = self.dashboard.serial.worker
        worker._abrir_porta = self.placa.abrir
        worker._listar_portas = lambda: [(PORTA, "Placa simulada", True)]
        worker.TEMPO_BANNER_S = 0.5
        worker.TEMPO_FIM_BANNER_S = 0.1
        worker.PRAZO_RELE_S = 0.5
        self.assertTrue(esperar(lambda: self.dashboard._disjuntor_carregado))

    def tearDown(self):
        self.dashboard.serial.encerrar()
        self.dashboard.banco.encerrar()
        QMessageBox.question = self._pergunta_original
        if self.dashboard._aviso_rele is not None:
            self.dashboard._aviso_rele.close()
        self.janela.deleteLater()
        app.processEvents()
        Database.PASTA_DATA, Database.CAMINHO, ConfigManager._dados = self._originais
        self._pasta.cleanup()

    def conectar(self):
        self.dashboard.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.dashboard.serial.esta_conectado()))
        self.assertTrue(esperar(lambda: len(self.dashboard.grafico._pontos) > 50))

    def eventos(self, tipo):
        return [evento for evento in EventoRepository.listar_todos() if evento.tipo == tipo]

    def test_placa_que_liga_com_rele_desligado_abre_o_disjuntor(self):
        self.assertEqual(status_no_banco(), Dispositivo.FECHADO)
        self.conectar()

        self.assertTrue(esperar(lambda: status_no_banco() == Dispositivo.ABERTO))
        self.assertFalse(self.dashboard.disjuntor.esta_fechado())
        self.assertIn("ABERTO", self.dashboard.ui.label_disjuntor_status.text())
        self.assertTrue(self.dashboard.ui.btn_religar_disjuntor.isEnabled())
        descricoes = [e.descricao for e in self.eventos(EventoHistorico.MUDANCA_DISJUNTOR)]
        self.assertTrue(any("conectou com o relé desligado" in d for d in descricoes), descricoes)
        # A aplicação nunca religa sozinha: nenhum !1 foi para a placa.
        self.assertNotIn("!1", self.placa.comandos)

    def test_banco_ja_aberto_nao_gera_evento_ao_conectar(self):
        DispositivoRepository.atualizar_status(Dispositivo.TAG_DISJUNTOR_PRINCIPAL, Dispositivo.ABERTO)
        self.dashboard.banco.carregar_disjuntor()
        self.assertTrue(esperar(lambda: not self.dashboard.disjuntor.esta_fechado()))
        self.conectar()
        esperar(lambda: False, timeout_s=0.3)
        self.assertEqual(self.eventos(EventoHistorico.MUDANCA_DISJUNTOR), [])

    def test_rele_que_muda_sozinho_abre_o_disjuntor_e_avisa(self):
        self.conectar()
        self.dashboard.ui.btn_religar_disjuntor.click()
        self.assertTrue(esperar(lambda: status_no_banco() == Dispositivo.FECHADO))
        self.assertTrue(esperar(lambda: self.dashboard.disjuntor.esta_fechado()))

        self.placa.rele = 0  # sem comando: como o Uno reiniciando com o relé desligado
        self.assertTrue(esperar(lambda: status_no_banco() == Dispositivo.ABERTO))
        self.assertFalse(self.dashboard.disjuntor.esta_fechado())
        self.assertTrue(self.dashboard._aviso_rele.isVisible())
        self.assertIn("DESLIGADO", self.dashboard._aviso_rele.text())
        self.assertTrue(esperar(lambda: self.eventos(EventoHistorico.RELE_ESPONTANEO)))

    def test_telemetria_chega_ao_grafico_em_tempo_real(self):
        self.conectar()
        _, potencia = self.dashboard.grafico._pontos[-1]
        # A0 = 900 -> 10,56 V; A1 = 700 -> 13,92 A; P = 147 W.
        self.assertAlmostEqual(potencia, 147.0, delta=1.0)
        self.assertIn("recebendo", self.dashboard.ui.label_status_grafico.text())

        self.dashboard.serial.desconectar()
        self.assertTrue(esperar(lambda: "desconectada" in self.dashboard.ui.label_status_grafico.text()))


if __name__ == "__main__":
    unittest.main()
