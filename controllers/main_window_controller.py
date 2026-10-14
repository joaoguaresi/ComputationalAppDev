import logging
from collections import deque

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QTableWidgetItem
import pyqtgraph as pg

from controllers.comandos_controller import ComandosController
from models.disjuntor import Disjuntor
from models.medicao import Medicao
from models.simulador_telemetria import SimuladorTelemetria
from ui.main_window import Ui_JanelaPrincipal

logger = logging.getLogger("smartgrid")


class MainWindowController:
    AMOSTRAS_GRAFICO = 60
    INTERVALO_SIMULACAO_MS = 2000
    ALTURA_MINIMA_GRAFICO = 180
    ALTURA_MINIMA_TABELA = 80
    ALTURA_INDICADORES = 44
    ALTURA_BOTOES = 26
    ALTURA_BOTAO_CORTE = 34

    def __init__(self, janela):
        self.janela = janela
        self.ui = Ui_JanelaPrincipal()
        self.ui.setupUi(janela)
        self._ajustar_layout()

        self.simulador = SimuladorTelemetria()
        self.disjuntor = Disjuntor()
        self.medicoes = self._pre_carregar_medicoes()

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

    def _ajustar_layout(self):
        """Abre a janela maximizada e entrega ao gráfico a maior parte da altura livre."""
        ui = self.ui
        self.janela.setWindowState(Qt.WindowMaximized)
        self._compactar_parte_superior()

        ui.grafico_tendencia.setMinimumHeight(self.ALTURA_MINIMA_GRAFICO)
        ui.tabela_historico.setMinimumHeight(self.ALTURA_MINIMA_TABELA)
        ui.layout_principal.setStretchFactor(ui.group_grafico, 2)
        ui.layout_principal.setStretchFactor(ui.group_historico, 1)
        for coluna in range(4):
            ui.grid_indicadores.setColumnStretch(coluna, 1)

    def _compactar_parte_superior(self):
        """Reduz espaçamentos e alturas dos indicadores e painéis para sobrar espaço ao gráfico."""
        ui = self.ui
        ui.label_titulo.setStyleSheet("font-size: 13pt; font-weight: bold;")
        ui.layout_principal.setSpacing(6)
        ui.layout_principal.setContentsMargins(10, 6, 10, 6)
        ui.grid_indicadores.setVerticalSpacing(2)

        for layout in (ui.grid_comandos, ui.grid_serial, ui.layout_grafico, ui.layout_historico):
            layout.setContentsMargins(6, 4, 6, 6)
        for grid in (ui.grid_comandos, ui.grid_serial):
            grid.setVerticalSpacing(4)

        # "Religar disjuntor" e "Configurar Regras de Alerta" lado a lado, economizando uma linha.
        for coluna, botao in enumerate((ui.btn_religar_disjuntor, ui.btn_regras_alerta)):
            ui.grid_comandos.removeWidget(botao)
            ui.grid_comandos.addWidget(botao, 4, coluna)

        for widget in (ui.lcd_tensao, ui.lcd_corrente, ui.lcd_potencia, ui.label_disjuntor_status):
            widget.setMinimumHeight(self.ALTURA_INDICADORES)
        for widget in (ui.btn_religar_disjuntor, ui.btn_regras_alerta, ui.btn_conectar, ui.btn_desconectar,
                       ui.label_alerta_status, ui.label_serial_status):
            widget.setMinimumHeight(self.ALTURA_BOTOES)
        ui.btn_corte_emergencia.setMinimumHeight(self.ALTURA_BOTAO_CORTE)

    def _pre_carregar_medicoes(self):
        """Gera o histórico inicial com a janela inteira do gráfico já preenchida.

        A deque tem tamanho máximo fixo: cada nova medição empurra a mais antiga
        para fora, então o gráfico desliza sem nunca ficar vazio ou pela metade.
        """
        intervalo = self.INTERVALO_SIMULACAO_MS / 1000
        historico = self.simulador.gerar_historico(self.AMOSTRAS_GRAFICO, intervalo)
        logger.info("Gráfico de telemetria pré-carregado com %d amostras.", len(historico))
        return deque(historico, maxlen=self.AMOSTRAS_GRAFICO)

    def _configurar_grafico(self):
        grafico = self.ui.grafico_tendencia
        grafico.setBackground("w")
        grafico.showGrid(x=True, y=True, alpha=0.3)
        grafico.setLabel("bottom", "Tempo em relação à última leitura (s)")
        grafico.setLabel("left", "Potência (W)")

        # Eixo X fixo: a amostra mais recente fica em 0 s e as anteriores à esquerda.
        intervalo = self.INTERVALO_SIMULACAO_MS / 1000
        inicio = -(self.AMOSTRAS_GRAFICO - 1) * intervalo
        self.eixo_x = [inicio + indice * intervalo for indice in range(self.AMOSTRAS_GRAFICO)]
        grafico.setXRange(inicio, 0, padding=0)

        self.curva_potencia = grafico.plot(pen=pg.mkPen("#9B59B6", width=2))

    def _redesenhar_grafico(self):
        potencias = [medicao.calcular_potencia() for medicao in self.medicoes]
        self.curva_potencia.setData(self.eixo_x, potencias)

    def _configurar_tabela_historico(self):
        self.ui.tabela_historico.setColumnWidth(0, 150)
        self.ui.tabela_historico.setColumnWidth(1, 180)

    def _registrar_linha_historico(self, evento):
        tabela = self.ui.tabela_historico
        linha = 0
        tabela.insertRow(linha)
        for coluna, valor in enumerate(evento.get_linha_tabela()):
            item = QTableWidgetItem(valor)
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

        self._redesenhar_grafico()
        self._atualizar_indicadores(medicao)
        self._atualizar_disjuntor()
        self.comandos.avaliar_protecao(medicao)
