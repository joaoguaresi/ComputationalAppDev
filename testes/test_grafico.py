"""Testes do Bloco 4: gráfico em dois modos (tempo real e histórico).

O GraficoController roda com a tela de verdade (Ui_JanelaPrincipal) em modo offscreen,
sem abrir janela, e com um banco falso no lugar do BancoController: o teste decide
quando e com o que cada consulta é respondida.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import logging
import unittest
from datetime import datetime, timedelta

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from controllers.grafico_controller import GraficoController
from models.config_manager import ConfigManager
from models.filtro_historico import FiltroHistorico
from models.leitura_media import LeituraMedia
from models.leitura_telemetria import LeituraTelemetria
from ui.main_window import Ui_JanelaPrincipal

logging.getLogger("smartgrid").addHandler(logging.NullHandler())

app = QApplication.instance() or QApplication([])
TEM_WIDGETS = isinstance(app, QApplication)


class BancoFalso(QObject):
    """Mesma interface de consulta do BancoController: devolve o número do pedido na hora
    e responde só quando o teste mandar."""

    historico_consultado = Signal(int, list, int)
    historico_falhou = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.pedidos = []

    def consultar_historico(self, filtro):
        self.pedidos.append(filtro)
        return len(self.pedidos)

    def responder(self, pedido, leituras, agrupar=1):
        self.historico_consultado.emit(pedido, leituras, agrupar)


def leituras(quantidade, fim=None, passo_ms=500, potencia=100.0):
    fim = fim or datetime.now()
    fim_ms = LeituraMedia.para_ms(fim)
    return [
        LeituraMedia(fim_ms - (quantidade - 1 - i) * passo_ms, 12.0, potencia / 12.0, potencia, 100)
        for i in range(quantidade)
    ]


class TestValidacaoDoFiltro(unittest.TestCase):
    AGORA = datetime(2026, 11, 20, 14, 0, 0)

    def test_inicio_depois_do_fim_e_recusado(self):
        filtro = FiltroHistorico.intervalo(self.AGORA, self.AGORA - timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "anterior"):
            GraficoController.validar_filtro(filtro, self.AGORA)

    def test_inicio_no_futuro_e_recusado(self):
        filtro = FiltroHistorico.intervalo(self.AGORA + timedelta(hours=1), self.AGORA + timedelta(hours=2))
        with self.assertRaisesRegex(ValueError, "futuro"):
            GraficoController.validar_filtro(filtro, self.AGORA)

    def test_quantidade_fora_da_faixa_e_recusada(self):
        with self.assertRaises(ValueError):
            GraficoController.validar_filtro(FiltroHistorico.ultimas(0), self.AGORA)

    def test_filtros_validos_passam(self):
        GraficoController.validar_filtro(FiltroHistorico.ultimas(500), self.AGORA)
        GraficoController.validar_filtro(
            FiltroHistorico.intervalo(self.AGORA - timedelta(hours=1), self.AGORA + timedelta(hours=1)), self.AGORA
        )


class TestLacunas(unittest.TestCase):
    def test_buraco_maior_que_o_limite_vira_nan(self):
        horarios = np.array([0.0, 0.5, 1.0, 30.0, 30.5])
        valores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        x, y = GraficoController._com_lacunas(horarios, valores, 2.0)
        self.assertEqual(len(x), 6)
        self.assertTrue(np.isnan(y[3]))
        self.assertTrue(np.all(np.diff(x) >= 0))  # o eixo X continua em ordem

    def test_sem_buraco_nada_muda(self):
        horarios = np.array([0.0, 0.5, 1.0])
        x, y = GraficoController._com_lacunas(horarios, np.array([1.0, 2.0, 3.0]), 2.0)
        self.assertEqual(len(x), 3)
        self.assertFalse(np.isnan(y).any())


@unittest.skipUnless(TEM_WIDGETS, "outro teste já criou uma QCoreApplication sem widgets")
class TesteGrafico(unittest.TestCase):
    def setUp(self):
        self._config = ConfigManager._dados
        ConfigManager._dados = dict(ConfigManager.DEFAULTS)
        self._aviso_original = QMessageBox.warning
        self.avisos = []
        QMessageBox.warning = staticmethod(lambda *args, **kwargs: self.avisos.append(args[2]))

        self.janela = QMainWindow()
        self.ui = Ui_JanelaPrincipal()
        self.ui.setupUi(self.janela)
        self.banco = BancoFalso()
        self.grafico = GraficoController(self.janela, self.ui, self.banco)

    def tearDown(self):
        QMessageBox.warning = self._aviso_original
        ConfigManager._dados = self._config
        self.janela.deleteLater()

    def pontos_na_curva(self):
        # xData são os dados entregues à curva; o getData() devolve só o trecho desenhado
        # (setClipToView e downsampling).
        x = self.grafico.curva_potencia.xData
        return 0 if x is None else len(x)


class TestPreCargaEConsulta(TesteGrafico):
    def test_pre_carga_pede_a_janela_do_grafico(self):
        filtro = self.banco.pedidos[0]
        self.assertEqual(filtro.modo, FiltroHistorico.ULTIMAS)
        self.assertEqual(filtro.quantidade, 120)  # 60 s com janelas de 500 ms
        self.banco.responder(1, leituras(120))
        self.assertEqual(self.pontos_na_curva(), 120)

    def test_entrar_no_historico_consulta_o_filtro_da_tela(self):
        self.ui.radio_historico.setChecked(True)
        self.assertEqual(len(self.banco.pedidos), 2)
        self.assertEqual(self.banco.pedidos[1].quantidade, self.ui.spin_quantidade.value())

    def test_resposta_de_consulta_antiga_e_descartada(self):
        self.banco.responder(1, leituras(120))
        self.ui.radio_historico.setChecked(True)   # pedido 2
        self.ui.btn_consultar.click()              # pedido 3 substitui o 2
        self.banco.responder(2, leituras(10))
        self.assertEqual(self.pontos_na_curva(), 0)
        self.banco.responder(3, leituras(30))
        self.assertEqual(self.pontos_na_curva(), 30)

    def test_trocar_de_modo_troca_a_curva(self):
        self.banco.responder(1, leituras(120))
        self.ui.radio_historico.setChecked(True)
        self.banco.responder(2, leituras(500))
        self.assertEqual(self.pontos_na_curva(), 500)
        self.ui.radio_tempo_real.setChecked(True)
        self.assertEqual(self.pontos_na_curva(), 120)

    def test_filtro_invalido_nao_chega_ao_banco(self):
        self.ui.radio_historico.setChecked(True)
        self.ui.radio_intervalo.setChecked(True)
        agora = datetime.now()
        self.ui.datetime_inicio.setDateTime(agora)
        self.ui.datetime_fim.setDateTime(agora - timedelta(minutes=5))
        pedidos = len(self.banco.pedidos)
        self.ui.btn_consultar.click()
        self.assertEqual(len(self.banco.pedidos), pedidos)
        self.assertEqual(len(self.avisos), 1)

    def test_aviso_de_consultando_ate_a_resposta(self):
        self.ui.radio_historico.setChecked(True)
        self.assertIn("consultando", self.ui.label_status_grafico.text())
        self.banco.responder(2, leituras(50))
        self.assertNotIn("consultando", self.ui.label_status_grafico.text())
        self.assertIn("50", self.ui.label_status_grafico.text())

    def test_eixo_x_em_data_hora(self):
        fim = datetime(2026, 11, 20, 14, 0, 0)
        self.banco.responder(1, leituras(3, fim=fim))
        x = self.grafico.curva_potencia.xData
        self.assertAlmostEqual(x[-1], fim.timestamp(), places=3)  # segundos desde 1970, não relativo

    def test_falha_da_consulta_avisa_o_operador(self):
        self.ui.radio_historico.setChecked(True)
        self.banco.historico_falhou.emit(2, "o banco está ocupado por outra conexão (database is locked)")
        self.assertIn("database is locked", self.avisos[-1])



class TestTempoReal(TesteGrafico):
    def lote(self, inicio, quantidade, passo_s=0.005):
        return [LeituraTelemetria(12.0, 10.0, 1, 0, inicio + timedelta(seconds=i * passo_s)) for i in range(quantidade)]

    def test_lote_da_serial_entra_na_curva(self):
        self.banco.responder(1, [])
        self.grafico.adicionar_leituras(self.lote(datetime.now(), 20))
        self.assertEqual(self.pontos_na_curva(), 20)
        self.assertIn("recebendo", self.ui.label_status_grafico.text())

    def test_janela_desliza_e_guarda_so_os_ultimos_60_s(self):
        inicio = datetime.now() - timedelta(seconds=90)
        for segundo in range(90):
            self.grafico.adicionar_leituras(self.lote(inicio + timedelta(seconds=segundo), 10, passo_s=0.1))
        horarios = [x for x, _ in self.grafico._pontos]
        self.assertLessEqual(horarios[-1] - horarios[0], GraficoController.JANELA_S)
        self.assertEqual(len(horarios), 601)  # 60 s a 10 pontos por segundo, com as duas pontas

    def test_no_historico_os_pontos_continuam_chegando_sem_redesenhar(self):
        self.banco.responder(1, [])
        self.ui.radio_historico.setChecked(True)
        self.banco.responder(2, leituras(5))
        self.grafico.adicionar_leituras(self.lote(datetime.now(), 20))
        self.assertEqual(self.pontos_na_curva(), 5)        # a curva continua sendo a do histórico
        self.ui.radio_tempo_real.setChecked(True)
        self.assertEqual(self.pontos_na_curva(), 20)       # e o tempo real está em dia

    def test_pre_carga_atrasada_nao_apaga_o_tempo_real(self):
        agora = datetime.now()
        self.grafico.adicionar_leituras(self.lote(agora, 20))
        self.banco.responder(1, leituras(10, fim=agora - timedelta(seconds=1)))
        self.assertEqual(len(self.grafico._pontos), 30)

    def test_placa_desconectada_avisa_no_status(self):
        self.grafico.adicionar_leituras(self.lote(datetime.now(), 20))
        self.grafico.placa_desconectada("cabo USB desconectado")
        self.assertIn("desconectada", self.ui.label_status_grafico.text())
        self.assertEqual(self.ui.label_status_grafico.toolTip(), "cabo USB desconectado")


if __name__ == "__main__":
    unittest.main()
