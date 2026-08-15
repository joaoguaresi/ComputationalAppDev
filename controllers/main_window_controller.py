from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTableWidgetItem
import pyqtgraph as pg

from controllers.comandos_controller import ComandosController
from models.disjuntor import Disjuntor
from models.medicao import Medicao
from models.simulador_telemetria import SimuladorTelemetria
from ui.main_window import Ui_JanelaPrincipal


class MainWindowController:
    LIMITE_PONTOS_GRAFICO = 120
    INTERVALO_SIMULACAO_MS = 2000

    def __init__(self, janela):
        self.janela = janela
        self.ui = Ui_JanelaPrincipal()
        self.ui.setupUi(janela)
        self.ui.layout_principal.setStretchFactor(self.ui.group_grafico, 1)
        for coluna in range(4):
            self.ui.grid_indicadores.setColumnStretch(coluna, 1)

        self.simulador = SimuladorTelemetria()
        self.disjuntor = Disjuntor()
        self.medicoes = self.simulador.gerar_historico(intervalo_segundos=self.INTERVALO_SIMULACAO_MS / 1000)

        self.comandos = ComandosController(self.janela, self.ui, self.disjuntor)
        self.comandos.estado_disjuntor_alterado.connect(self._atualizar_disjuntor)
        self.comandos.evento_registrado.connect(self._registrar_linha_historico)

        self._configurar_grafico()
        self._configurar_tabela_historico()
        self._redesenhar_grafico()
        self._atualizar_indicadores(self.medicoes[-1])
        self._atualizar_disjuntor()
        self.comandos.avaliar_protecao(self.medicoes[-1])

        self.timer = QTimer(self.janela)
        self.timer.timeout.connect(self._simular_nova_medicao)
        self.timer.start(self.INTERVALO_SIMULACAO_MS)

    def _configurar_grafico(self):
        grafico = self.ui.grafico_tendencia
        grafico.setBackground("w")
        grafico.showGrid(x=True, y=True, alpha=0.3)
        grafico.setLabel("bottom", "Tempo (s)")
        grafico.setLabel("left", "Potência (W)")

        self.curva_potencia = grafico.plot(pen=pg.mkPen("#9B59B6", width=2))

    def _redesenhar_grafico(self):
        series = SimuladorTelemetria.extrair_series(self.medicoes)
        inicio = series["segundos"][0]
        eixo_x = [segundo - inicio for segundo in series["segundos"]]
        self.curva_potencia.setData(eixo_x, series["potencia"])

    def _configurar_tabela_historico(self):
        self.ui.tabela_historico.setColumnWidth(0, 150)
        self.ui.tabela_historico.setColumnWidth(1, 180)

    def _registrar_linha_historico(self, evento):
        tabela = self.ui.tabela_historico
        linha = 0
        tabela.insertRow(linha)
        for coluna, valor in enumerate(evento.get_linha_tabela()):
            item = QTableWidgetItem(str(valor))
            tabela.setItem(linha, coluna, item)

    def _atualizar_indicadores(self, medicao):
        dados = medicao.get_dados()
        self.ui.lcd_tensao.display(dados["tensao"])
        self.ui.lcd_corrente.display(dados["corrente"])
        self.ui.lcd_potencia.display(dados["potencia"])

    def _atualizar_disjuntor(self):
        dados = self.disjuntor.get_dados()
        self.ui.label_disjuntor_status.setText(dados["texto"])
        self.ui.label_disjuntor_status.setStyleSheet(
            f"background-color: {dados['cor']}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )

    def _simular_nova_medicao(self):
        medicao = self.simulador.proxima_medicao()
        if not self.comandos.carga_esta_ativa():
            medicao = Medicao(medicao.tensao_v, 0.0, medicao.timestamp)

        self.medicoes.append(medicao)
        if len(self.medicoes) > self.LIMITE_PONTOS_GRAFICO:
            self.medicoes = self.medicoes[-self.LIMITE_PONTOS_GRAFICO:]

        self._redesenhar_grafico()
        self._atualizar_indicadores(medicao)
        self._atualizar_disjuntor()
        self.comandos.avaliar_protecao(medicao)
