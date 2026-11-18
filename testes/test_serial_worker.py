"""Testes do Bloco 3: thread serial, handshake, relé e resiliência.

Rodam o SerialWorker numa QThread de verdade, ligado a uma PlacaSimulada que imita o
firmware do professor: não precisam do Arduino. Os tempos de espera do worker são
encurtados para os testes andarem rápido.
"""

import logging
import time
import unittest

from PySide6.QtCore import QCoreApplication

from controllers.serial_controller import SerialController
from models.config_manager import ConfigManager
from models.configuracao_serial import ConfiguracaoSerial
from testes.placa_simulada import PlacaSimulada

logging.getLogger("smartgrid").addHandler(logging.NullHandler())

app = QCoreApplication.instance() or QCoreApplication([])

PORTA = "COM9"
DESCONECTADO = ConfiguracaoSerial.DESCONECTADO
CONECTANDO = ConfiguracaoSerial.CONECTANDO


def esperar(condicao, timeout_s=3.0) -> bool:
    """Processa os eventos do Qt (é assim que os sinais da thread serial chegam) até a condição valer."""
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        app.processEvents()
        if condicao():
            return True
        time.sleep(0.005)
    app.processEvents()
    return condicao()


class TesteSerial(unittest.TestCase):
    """Base: cria a placa simulada e o SerialController e guarda tudo o que ele emite."""

    SINAIS = ("estado_alterado", "portas_listadas", "conectado", "desconectado", "falha_conexao")

    def criar_placa(self):
        return PlacaSimulada()

    def encurtar_tempos(self, worker):
        worker.ESPERA_FILA_S = 0.02

    def setUp(self):
        # Configuração só em memória: o worker lê o config.json, e o de verdade não pode mudar.
        self._config_original = ConfigManager._dados
        ConfigManager._dados = dict(ConfigManager.DEFAULTS)

        self.placa = self.criar_placa()
        self.serial = SerialController(abrir_porta=self.placa.abrir, listar_portas=lambda: [PORTA])
        self.encurtar_tempos(self.serial.worker)

        self.sinais = []
        for nome in self.SINAIS:
            getattr(self.serial, nome).connect(lambda *args, nome=nome: self.sinais.append((nome, args)))
        self.serial.iniciar()

    def tearDown(self):
        self.serial.encerrar()
        ConfigManager._dados = self._config_original

    def recebidos(self, nome):
        return [args for sinal, args in self.sinais if sinal == nome]

    def estados(self):
        return [args[0] for args in self.recebidos("estado_alterado")]


class TestMaquinaDeEstados(TesteSerial):
    def test_comeca_desconectado_e_lista_as_portas(self):
        self.assertTrue(esperar(lambda: self.recebidos("portas_listadas")))
        self.assertEqual(self.recebidos("portas_listadas")[0], ([PORTA],))
        self.assertEqual(self.estados()[0], DESCONECTADO)

    def test_conectar_abre_a_porta_em_9600(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: CONECTANDO in self.estados()))
        self.assertTrue(self.placa.aberta)
        self.assertEqual(self.placa.baudrate, 9600)

    def test_porta_que_nao_abre_vira_falha_de_conexao(self):
        self.placa.puxar_cabo()
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.recebidos("falha_conexao")))
        self.assertIn("não existe", self.recebidos("falha_conexao")[0][0])
        self.assertEqual(self.serial.estado, DESCONECTADO)

    def test_desconectar_fecha_a_porta(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.placa.aberta))
        self.serial.desconectar()
        self.assertTrue(esperar(lambda: self.recebidos("desconectado")))
        self.assertFalse(self.placa.aberta)
        self.assertEqual(self.serial.estado, DESCONECTADO)

    def test_pedidos_sao_atendidos_na_ordem_da_fila(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.serial.desconectar()
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.serial.estado == CONECTANDO and self.placa.aberta))

    def test_encerrar_termina_a_thread(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.placa.aberta))
        self.serial.encerrar()
        self.assertFalse(self.serial.thread_serial.isRunning())
        self.assertFalse(self.placa.aberta)


if __name__ == "__main__":
    unittest.main()
