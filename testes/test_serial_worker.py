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
from models.leitor_linhas import LeitorLinhas
from testes.placa_simulada import PlacaSimulada

logging.getLogger("smartgrid").addHandler(logging.NullHandler())

app = QCoreApplication.instance() or QCoreApplication([])

PORTA = "COM9"
DESCONECTADO = ConfiguracaoSerial.DESCONECTADO
CONECTANDO = ConfiguracaoSerial.CONECTANDO
NEGOCIANDO = ConfiguracaoSerial.NEGOCIANDO
CALIBRANDO = ConfiguracaoSerial.CALIBRANDO
CONECTADO = ConfiguracaoSerial.CONECTADO


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
        worker.TEMPO_BANNER_S = 0.5
        worker.TEMPO_FIM_BANNER_S = 0.1
        worker.TEMPO_PRIMEIRA_TELEMETRIA_S = 0.5
        worker.AMOSTRAS_CALIBRACAO = 10
        worker.TEMPO_CALIBRACAO_S = 0.3

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

    def conectar(self, taxa=115200):
        """Faz o handshake completo e espera a telemetria ser liberada."""
        self.serial.conectar(PORTA, taxa, 1000)
        self.assertTrue(esperar(lambda: self.serial.estado == CONECTADO), f"estados: {self.estados()}")


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
        self.assertTrue(esperar(lambda: self.serial.estado != DESCONECTADO and self.placa.aberta))

    def test_encerrar_termina_a_thread(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.placa.aberta))
        self.serial.encerrar()
        self.assertFalse(self.serial.thread_serial.isRunning())
        self.assertFalse(self.placa.aberta)


class TestBannerEComandoDeTaxa(TesteSerial):
    def criar_placa(self):
        # Atraso do bootloader encurtado, mas ainda maior que zero.
        return PlacaSimulada(atraso_banner_s=0.15)

    def test_espera_o_banner_e_depois_envia_o_comando_de_taxa(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: NEGOCIANDO in self.estados()))
        self.assertEqual(self.placa.comandos[0], "!S115200\n")
        # Nada é enviado durante o bootloader: o !S vai só depois do banner.
        self.assertGreaterEqual(self.placa.momentos_comandos[0], self.placa.banner_enviado_em)


class TestSemBanner(TesteSerial):
    def criar_placa(self):
        return PlacaSimulada(enviar_banner=False)

    def test_sem_banner_o_comando_de_taxa_vai_assim_mesmo(self):
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: NEGOCIANDO in self.estados()))
        self.assertEqual(self.placa.comandos, ["!S115200\n"])

    def test_desconectar_interrompe_a_espera_do_banner(self):
        self.serial.worker.TEMPO_BANNER_S = 10.0
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.placa.aberta))
        inicio = time.monotonic()
        self.serial.desconectar()
        self.assertTrue(esperar(lambda: self.recebidos("desconectado"), timeout_s=1.0))
        self.assertLess(time.monotonic() - inicio, 1.0)
        self.assertFalse(self.placa.aberta)
        self.assertEqual(self.placa.comandos, [])


class TestAckETrocaDeTaxa(TesteSerial):
    def test_ack_troca_a_taxa_sem_fechar_a_porta(self):
        self.conectar()
        self.assertEqual(self.recebidos("conectado"), [(PORTA, 115200, False)])
        self.assertEqual(self.placa.baudrate, 115200)
        # A mesma porta, sem reabrir: reabrir reiniciaria o Uno.
        self.assertEqual(self.placa.aberturas, 1)
        self.assertEqual(self.estados()[-4:], [CONECTANDO, NEGOCIANDO, CALIBRANDO, CONECTADO])

    def test_as_quatro_taxas(self):
        for taxa in (9600, 19200, 38400, 115200):
            with self.subTest(taxa=taxa):
                self.conectar(taxa)
                self.assertEqual(self.placa.comandos[-1], f"!S{taxa}\n")
                self.assertEqual(self.placa.baudrate, taxa)
                self.serial.desconectar()
                self.assertTrue(esperar(lambda: self.serial.estado == DESCONECTADO))

    def test_err_da_placa_vira_falha_e_fecha_a_porta(self):
        self.placa.recusar_taxa = True
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.recebidos("falha_conexao")))
        self.assertIn("recusou", self.recebidos("falha_conexao")[0][0])
        self.assertFalse(self.placa.aberta)
        self.assertEqual(self.serial.estado, DESCONECTADO)

    def test_placa_que_nao_responde_ao_comando_de_taxa(self):
        self.placa.responder_taxa = False
        self.serial.conectar(PORTA, 115200, 200)
        self.assertTrue(esperar(lambda: self.recebidos("falha_conexao")))
        self.assertIn("não respondeu", self.recebidos("falha_conexao")[0][0])

    def test_ack_sem_telemetria_vira_falha(self):
        self.placa.transmitir_apos_ack = False
        self.serial.conectar(PORTA, 115200, 1000)
        self.assertTrue(esperar(lambda: self.recebidos("falha_conexao")))
        self.assertIn("telemetria não chegou", self.recebidos("falha_conexao")[0][0])


class TestCalibracaoDoZero(TesteSerial):
    def test_calibra_o_zero_com_o_rele_desligado(self):
        self.placa.a1 = 520
        self.conectar()
        self.assertAlmostEqual(self.serial.worker._calibracao.zero_corrente_adc, 520.0)

    def test_zero_longe_do_meio_da_escala_e_descartado(self):
        self.placa.a1 = 700
        self.conectar()
        self.assertAlmostEqual(self.serial.worker._calibracao.zero_corrente_adc, 512.0)

    def test_calibracao_desligada_no_config(self):
        ConfigManager._dados["calibrar_zero_corrente"] = False
        self.placa.a1 = 520
        self.conectar()
        self.assertAlmostEqual(self.serial.worker._calibracao.zero_corrente_adc, 512.0)

    def test_rele_ligado_mantem_o_zero_do_config(self):
        self.placa.rele_ao_ligar = 1
        self.placa.a1 = 520
        self.conectar()
        self.assertAlmostEqual(self.serial.worker._calibracao.zero_corrente_adc, 512.0)


class TestTelemetria(TesteSerial):
    SINAIS = TesteSerial.SINAIS + ("leituras_recebidas", "conexao_perdida")

    def encurtar_tempos(self, worker):
        super().encurtar_tempos(worker)
        worker.TEMPO_SILENCIO_S = 0.3

    def leituras(self):
        return [leitura for (lote,) in self.recebidos("leituras_recebidas") for leitura in lote]

    def test_leituras_chegam_em_lote_ja_convertidas(self):
        self.placa.a0 = 1023
        self.conectar()
        self.assertTrue(esperar(lambda: len(self.recebidos("leituras_recebidas")) >= 3))
        lote = self.recebidos("leituras_recebidas")[1][0]
        # Uns 20 pacotes por lote a 200 Hz, nunca um sinal por pacote.
        self.assertGreater(len(lote), 5)
        self.assertAlmostEqual(lote[-1].tensao_v, 12.0)
        self.assertAlmostEqual(lote[-1].corrente_a, 0.0)
        self.assertEqual(lote[-1].a0, 1023)

    def test_pacotes_invalidos_sao_descartados_sem_parar_a_telemetria(self):
        self.conectar()
        for _ in range(5):
            self.placa.injetar("$DAT,512,717,1,0*56")  # um caractere trocado: checksum errado
        self.placa.injetar("ruido qualquer")
        self.assertTrue(esperar(lambda: self.serial.worker.total_descartados >= 6))
        quantas = len(self.leituras())
        self.assertTrue(esperar(lambda: len(self.leituras()) > quantas + 20))
        self.assertEqual(self.serial.estado, CONECTADO)

    def test_media_movel_suaviza_a_corrente(self):
        self.conectar()
        self.assertTrue(esperar(lambda: self.leituras()))
        self.placa.a1 = 612  # 100 contagens acima do zero: 7,4 A
        self.assertTrue(esperar(lambda: abs(self.leituras()[-1].corrente_a - 7.405) < 0.01))
        intermediarias = [leitura.corrente_a for leitura in self.leituras() if 0.1 < leitura.corrente_a < 7.3]
        self.assertTrue(intermediarias, "a corrente pulou direto para 7,4 A, sem média móvel")

    def test_watchdog_de_silencio_derruba_a_conexao(self):
        self.conectar()
        self.placa.silenciar()
        self.assertTrue(esperar(lambda: self.recebidos("conexao_perdida")))
        self.assertIn("nenhum pacote válido", self.recebidos("conexao_perdida")[0][0])
        self.assertFalse(self.placa.aberta)
        self.assertEqual(self.serial.estado, DESCONECTADO)

    def test_erro_na_porta_vira_conexao_perdida(self):
        self.conectar()
        self.placa.puxar_cabo()
        self.assertTrue(esperar(lambda: self.recebidos("conexao_perdida")))
        self.assertIn("erro na porta serial", self.recebidos("conexao_perdida")[0][0])
        self.assertEqual(self.serial.estado, DESCONECTADO)


class TestLeitorLinhas(unittest.TestCase):
    def test_pacote_partido_em_dois_pedacos(self):
        leitor = LeitorLinhas()
        self.assertEqual(leitor.adicionar(b"$DAT,512,7"), [])
        self.assertEqual(leitor.adicionar(b"16,1,0*56\r\n$DAT"), ["$DAT,512,716,1,0*56"])

    def test_varias_linhas_num_pedaco(self):
        leitor = LeitorLinhas()
        linhas = leitor.adicionar(b"PLACA EM ESPERA (9600 baud)\r\nEnvie !P\r\n")
        self.assertEqual(linhas, ["PLACA EM ESPERA (9600 baud)", "Envie !P"])

    def test_lixo_sem_quebra_de_linha_e_descartado(self):
        leitor = LeitorLinhas(tamanho_maximo=16)
        self.assertEqual(leitor.adicionar(b"\xf0" * 20), [])
        self.assertEqual(leitor.descartados, 1)
        self.assertEqual(leitor.adicionar(b"$DAT\n"), ["$DAT"])

    def test_byte_que_nao_e_ascii_vira_caractere_de_substituicao(self):
        self.assertEqual(LeitorLinhas().adicionar(b"\xf0$DAT\n"), ["�$DAT"])


if __name__ == "__main__":
    unittest.main()
