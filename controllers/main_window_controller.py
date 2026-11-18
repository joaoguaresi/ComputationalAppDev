import logging
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

from controllers.banco_controller import BancoController
from controllers.comandos_controller import ComandosController
from controllers.corte_controller import CorteController
from controllers.eventos_controller import EventosController
from controllers.limites_controller import LimitesController
from controllers.painel_serial_controller import PainelSerialController
from controllers.serial_controller import SerialController
from models.disjuntor import Disjuntor
from models.dispositivo import Dispositivo
from models.dispositivo_repository import DispositivoRepository
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
    DURACAO_AVISO_BANCO_MS = 10000

    def __init__(self, janela):
        self.janela = janela
        self.ui = Ui_JanelaPrincipal()
        self.ui.setupUi(janela)
        self._ajustar_layout()

        # Thread do banco: começa com o dashboard e é encerrada no aboutToQuit, que o Qt
        # emite antes de a aplicação fechar.
        self.banco = BancoController(self.janela)
        self.banco.falha_banco.connect(self._avisar_falha_banco)
        self.banco.iniciar()
        QApplication.instance().aboutToQuit.connect(self.banco.encerrar)

        # Thread serial: começa parada (DESCONECTADO) e conecta quando o operador pede.
        self.serial = SerialController(self.janela)
        self.serial.iniciar()
        QApplication.instance().aboutToQuit.connect(self.serial.encerrar)
        self.ultima_leitura = None

        self.simulador = SimuladorTelemetria()
        self.disjuntor = self._carregar_disjuntor()
        self.medicoes = self._pre_carregar_medicoes()

        self.historico = EventosController(self.janela, self.ui.tabela_historico, self.banco)
        self.comandos = ComandosController(self.janela, self.ui, self.disjuntor, self.historico)
        self.painel_serial = PainelSerialController(self.janela, self.ui, self.serial, self.historico)
        self.corte = CorteController(
            self.janela, self.ui, self.disjuntor, self.historico, self.banco, self._potencia_atual
        )
        self.corte.estado_disjuntor_alterado.connect(self._atualizar_disjuntor)
        self.corte.estado_disjuntor_alterado.connect(self.comandos.reavaliar_protecao)
        self.limites = LimitesController(self.janela, self.ui, self.historico)
        self._ligar_serial()

        self._configurar_grafico()
        self._redesenhar_grafico()
        # Os mostradores ficam em branco até a placa mandar a primeira leitura.
        self._limpar_indicadores()
        self._atualizar_disjuntor()
        self.comandos.reavaliar_protecao()

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

    def _ligar_serial(self):
        """Liga a thread serial ao dashboard.

        Cada lote de leituras vai para o banco (média por janela, no DatabaseWorker) e
        atualiza os mostradores, a proteção por setpoint e os limites de segurança. O
        !0/!1 do corte e do religamento vai para a placa, e o CorteController só grava a
        operação quando ela confirma (ACK e STATUS_RELE no valor pedido).
        """
        self.serial.leituras_recebidas.connect(self._ao_receber_leituras)
        self.serial.desconectado.connect(self._limpar_indicadores)
        self.serial.conexao_perdida.connect(self._limpar_indicadores)

        self.corte.comando_rele_solicitado.connect(self.serial.enviar_comando_rele)
        self.serial.rele_confirmado.connect(self.corte.confirmar_rele)
        self.serial.rele_nao_confirmado.connect(self.corte.recusar_rele)

    def _ao_receber_leituras(self, lote):
        """Lote de LeituraTelemetria da thread serial (uns 20 por vez, 10 vezes por segundo)."""
        self.banco.gravar_leituras(lote)
        leitura = lote[-1]
        self.ultima_leitura = leitura
        self._atualizar_indicadores(leitura)
        self.comandos.avaliar_protecao(leitura)
        self.limites.avaliar(leitura)

    def _limpar_indicadores(self, *_motivo):
        """Sem placa, os mostradores ficam em branco, em vez de congelar no último valor."""
        self.ultima_leitura = None
        for lcd in (self.ui.lcd_tensao, self.ui.lcd_corrente, self.ui.lcd_potencia):
            lcd.display("--")

    def _avisar_falha_banco(self, mensagem):
        """Aviso do DatabaseWorker (banco ocupado ou que não abriu). O detalhe já está no
        log; a barra de status não trava a tela, ao contrário de um QMessageBox."""
        self.janela.statusBar().showMessage(mensagem, self.DURACAO_AVISO_BANCO_MS)

    @staticmethod
    def _carregar_disjuntor():
        """Cria o disjuntor com o status gravado no banco, para o dashboard abrir no
        último estado conhecido em vez de sempre FECHADO."""
        tag = Dispositivo.TAG_DISJUNTOR_PRINCIPAL
        dispositivo = DispositivoRepository.buscar_por_tag(tag)
        if dispositivo is None:
            logger.warning("Disjuntor %s não encontrado no banco. Iniciando como FECHADO.", tag)
            return Disjuntor()

        logger.info("Estado do disjuntor %s carregado do banco: %s.", tag, dispositivo.status)
        return Disjuntor(dispositivo.status, dispositivo.ultima_atualizacao)

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

    def _potencia_atual(self) -> float:
        """Potência da leitura mais recente da placa, gravada no evento do corte de emergência."""
        if self.ultima_leitura is None:
            return 0.0
        return self.ultima_leitura.calcular_potencia()

    def _atualizar_indicadores(self, medicao):
        dados = medicao.get_dados()
        self.ui.lcd_tensao.display(dados["tensao"])
        self.ui.lcd_corrente.display(dados["corrente"])
        self.ui.lcd_potencia.display(dados["potencia"])

    def _atualizar_disjuntor(self):
        dados = self.disjuntor.get_dados()
        self.ui.label_disjuntor_status.setText(dados["texto"])
        self.ui.label_disjuntor_status.setToolTip(f"Última alteração: {dados['data_hora']}")
        self.ui.label_disjuntor_status.setStyleSheet(
            f"background-color: {dados['cor']}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )
