import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from controllers.banco_controller import BancoController
from controllers.comandos_controller import ComandosController
from controllers.corte_controller import CorteController
from controllers.eventos_controller import EventosController
from controllers.grafico_controller import GraficoController
from controllers.limites_controller import LimitesController
from controllers.painel_serial_controller import PainelSerialController
from controllers.serial_controller import SerialController
from models.disjuntor import Disjuntor
from models.dispositivo import Dispositivo
from models.evento_historico import EventoHistorico
from ui.main_window import Ui_JanelaPrincipal

logger = logging.getLogger("smartgrid")


class MainWindowController:
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

        # Thread serial: começa parada (DESCONECTADO) e conecta quando o operador pede.
        # Ligada ao aboutToQuit antes da do banco, para ser encerrada primeiro: quem
        # produz as leituras para antes de quem as grava, e o último lote ainda é gravado.
        self.serial = SerialController(self.janela)
        self.serial.iniciar()
        QApplication.instance().aboutToQuit.connect(self.serial.encerrar)
        self.ultima_leitura = None

        # Thread do banco: começa com o dashboard e é encerrada no aboutToQuit, que o Qt
        # emite antes de a aplicação fechar.
        self.banco = BancoController(self.janela)
        self.banco.falha_banco.connect(self._avisar_falha_banco)
        self.banco.iniciar()
        QApplication.instance().aboutToQuit.connect(self.banco.encerrar)

        # O status gravado do disjuntor é lido pelo DatabaseWorker; até a resposta, o
        # indicador mostra que está carregando (_ao_carregar_disjuntor).
        self.disjuntor = Disjuntor()
        self._disjuntor_carregado = False
        # STATUS_RELE que a placa informou antes de o disjuntor ser lido do banco.
        self._rele_pendente = None
        # Aviso não modal do relé que mudou sem comando, reaproveitado a cada mudança.
        self._aviso_rele = None

        self.historico = EventosController(self.janela, self.ui.tabela_historico, self.banco)
        self.comandos = ComandosController(self.janela, self.ui, self.disjuntor, self.historico)
        self.painel_serial = PainelSerialController(self.janela, self.ui, self.serial, self.historico)
        self.corte = CorteController(
            self.janela, self.ui, self.disjuntor, self.historico, self.banco, self._potencia_atual
        )
        self.corte.estado_disjuntor_alterado.connect(self._atualizar_disjuntor)
        self.corte.estado_disjuntor_alterado.connect(self.comandos.reavaliar_protecao)
        self.limites = LimitesController(self.janela, self.ui, self.historico, self.banco)
        self.grafico = GraficoController(self.janela, self.ui, self.banco)
        self._ligar_serial()

        # Os mostradores ficam em branco até a placa mandar a primeira leitura.
        self._limpar_indicadores()
        self._atualizar_disjuntor()
        self.comandos.reavaliar_protecao()
        self.banco.disjuntor_carregado.connect(self._ao_carregar_disjuntor)
        self.banco.carregar_disjuntor()

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
        atualiza o gráfico em tempo real, os mostradores, a proteção por setpoint e os
        limites de segurança. O !0/!1 do corte e do religamento vai para a placa, e o
        CorteController só grava a operação quando ela confirma (ACK e STATUS_RELE no
        valor pedido). O disjuntor da tela segue o STATUS_RELE da placa ao conectar e
        quando o relé muda sem comando.
        """
        self.serial.leituras_recebidas.connect(self._ao_receber_leituras)
        self.serial.desconectado.connect(self._limpar_indicadores)
        self.serial.conexao_perdida.connect(self._limpar_indicadores)
        self.serial.desconectado.connect(self.grafico.placa_desconectada)
        self.serial.conexao_perdida.connect(self.grafico.placa_desconectada)

        self.corte.comando_rele_solicitado.connect(self.serial.enviar_comando_rele)
        self.serial.rele_confirmado.connect(self.corte.confirmar_rele)
        self.serial.rele_nao_confirmado.connect(self.corte.recusar_rele)

        # Relé que mudou sem comando (o Uno reiniciou depois do cabo puxado, por exemplo)
        # e botão da bancada: os dois vão para o histórico pelo DatabaseWorker.
        self.serial.rele_espontaneo.connect(self.banco.registrar_rele_espontaneo)
        self.serial.botao_pressionado.connect(self._ao_pressionar_botao_local)

        # Disjuntor pelo STATUS_RELE. Ligado depois do registrar_rele_espontaneo: o evento
        # da mudança espontânea entra na fila do banco antes do evento do disjuntor.
        self.serial.rele_inicial.connect(self._ao_receber_rele_inicial)
        self.serial.rele_espontaneo.connect(self._ao_mudar_rele_sem_comando)
        self.banco.disjuntor_sincronizado.connect(self._ao_gravar_disjuntor_da_placa)
        self.banco.disjuntor_nao_sincronizado.connect(self._ao_falhar_disjuntor_da_placa)

    def _ao_receber_leituras(self, lote):
        """Lote de LeituraTelemetria da thread serial (uns 20 por vez, 10 vezes por segundo)."""
        self.banco.gravar_leituras(lote)
        self.grafico.adicionar_leituras(lote)
        leitura = lote[-1]
        self.ultima_leitura = leitura
        self._atualizar_indicadores(leitura)
        self.comandos.avaliar_protecao(leitura)
        self.limites.avaliar(leitura)

    def _ao_pressionar_botao_local(self, momento):
        """Botão da bancada (pino 11): disparo local do disjuntor.

        Faz o mesmo corte do botão da tela, sem a pergunta de confirmação: o !0 vai para
        a placa e a operação só é gravada quando ela confirma.
        """
        self.banco.registrar_botao_local(momento)
        if self.disjuntor.esta_fechado():
            self.corte.solicitar_corte()
        else:
            logger.info("Botão local pressionado com o disjuntor já aberto: nenhum comando enviado.")

    def _limpar_indicadores(self, *_motivo):
        """Sem placa, os mostradores ficam em branco, em vez de congelar no último valor."""
        self.ultima_leitura = None
        for lcd in (self.ui.lcd_tensao, self.ui.lcd_corrente, self.ui.lcd_potencia):
            lcd.display("--")

    def _avisar_falha_banco(self, mensagem):
        """Aviso do DatabaseWorker (banco ocupado ou que não abriu). O detalhe já está no
        log; a barra de status não trava a tela, ao contrário de um QMessageBox."""
        self.janela.statusBar().showMessage(mensagem, self.DURACAO_AVISO_BANCO_MS)

    def _ao_carregar_disjuntor(self, dispositivo, falha):
        """Status gravado do disjuntor, lido pelo DatabaseWorker: o dashboard abre no
        último estado conhecido em vez de sempre FECHADO."""
        tag = Dispositivo.TAG_DISJUNTOR_PRINCIPAL
        if dispositivo is not None:
            logger.info("Estado do disjuntor %s carregado do banco: %s.", tag, dispositivo.status)
            self.disjuntor.restaurar(dispositivo.status, dispositivo.ultima_atualizacao)
        elif falha:
            logger.warning("Estado do disjuntor %s não foi lido do banco (%s). Iniciando como FECHADO.", tag, falha)
        else:
            logger.warning("Disjuntor %s não encontrado no banco. Iniciando como FECHADO.", tag)

        self._disjuntor_carregado = True
        self._ao_mudar_disjuntor()

        if self._rele_pendente is not None:
            status_rele, self._rele_pendente = self._rele_pendente, None
            self._ao_receber_rele_inicial(status_rele)

    def _ao_mudar_disjuntor(self):
        """Atualiza tudo o que depende do estado do disjuntor: o indicador, a proteção
        por setpoint e os botões de corte e religamento."""
        self._atualizar_disjuntor()
        self.comandos.reavaliar_protecao()
        self.corte.atualizar_botoes()

    # ------------------------------------------------------------------
    # Disjuntor pelo STATUS_RELE da placa
    # ------------------------------------------------------------------

    @staticmethod
    def _estado_pelo_rele(status_rele) -> str:
        """STATUS_RELE 1 = relé ligado = disjuntor FECHADO; 0 = ABERTO.

        O LED da bancada acende ao contrário (o firmware usa o relé em nível baixo), mas o
        STATUS_RELE já vem certo no protocolo: não há nada a inverter aqui.
        """
        if status_rele == CorteController.RELE_LIGADO:
            return Disjuntor.FECHADO
        return Disjuntor.ABERTO

    def _ao_receber_rele_inicial(self, status_rele):
        """STATUS_RELE do primeiro pacote depois do Conectar.

        O Uno liga com o relé desligado, mas o banco pode ter o disjuntor FECHADO (a
        aplicação foi fechada com a carga ligada). A tela segue a placa: o disjuntor passa
        a ABERTO, com o evento no histórico, e o operador religa quando quiser. A
        aplicação nunca manda o !1 sozinha: ligar a carga é decisão do operador.
        """
        if not self._disjuntor_carregado:
            self._rele_pendente = status_rele
            return

        estado = self._estado_pelo_rele(status_rele)
        if estado == self.disjuntor.estado:
            logger.info("Relé da placa ao conectar (STATUS_RELE = %d) confere com o disjuntor %s.", status_rele, estado)
            return

        if estado == Disjuntor.ABERTO:
            descricao = f"Disjuntor aberto: a placa conectou com o relé desligado (STATUS_RELE = {status_rele})"
            aviso = "A placa conectou com o relé desligado: disjuntor ABERTO. Use Religar disjuntor para ligar a carga."
        else:
            descricao = f"Disjuntor fechado: a placa conectou com o relé ligado (STATUS_RELE = {status_rele})"
            aviso = "A placa conectou com o relé ligado: disjuntor FECHADO."
        self._sincronizar_disjuntor(estado, descricao)
        self.janela.statusBar().showMessage(aviso, self.DURACAO_AVISO_BANCO_MS)

    def _ao_mudar_rele_sem_comando(self, status_rele, momento):
        """O STATUS_RELE mudou sem comando do operador (por exemplo, o cabo USB foi puxado e
        o Uno reiniciou com o relé desligado).

        O evento da mudança espontânea já foi para o histórico pelo DatabaseWorker
        (registrar_rele_espontaneo). Aqui o disjuntor passa a seguir o relé e o operador
        recebe o aviso na tela.
        """
        momento = momento or datetime.now()
        if not self._disjuntor_carregado:
            self._rele_pendente = status_rele
        else:
            estado = self._estado_pelo_rele(status_rele)
            if estado != self.disjuntor.estado:
                if estado == Disjuntor.ABERTO:
                    descricao = "Disjuntor aberto: o relé desligou sem comando do operador"
                else:
                    descricao = "Disjuntor fechado: o relé ligou sem comando do operador"
                self._sincronizar_disjuntor(estado, descricao, momento)
        self._avisar_rele_sem_comando(status_rele, momento)

    def _sincronizar_disjuntor(self, estado, descricao, momento=None):
        """Põe o disjuntor no estado que a placa informou e pede a gravação ao banco.

        Diferente do corte, a tela muda antes do COMMIT: o relé já mudou de verdade, e
        mostrar o estado antigo enquanto o banco grava enganaria o operador. O banco grava
        o status do relé e do disjuntor junto com o evento, numa única transação.
        """
        if estado == Disjuntor.ABERTO:
            self.disjuntor.abrir()
        else:
            self.disjuntor.fechar()
        self._ao_mudar_disjuntor()

        logger.warning("Disjuntor passou a %s pelo STATUS_RELE da placa: %s.", estado, descricao)
        evento = EventoHistorico(
            EventoHistorico.MUDANCA_DISJUNTOR,
            descricao,
            timestamp=momento,
            dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
        )
        self.banco.sincronizar_disjuntor(estado, [evento])

    def _ao_gravar_disjuntor_da_placa(self, _status, eventos):
        """Depois do COMMIT: os eventos já gravados aparecem no histórico."""
        for evento in eventos:
            self.historico.publicar(evento)

    def _ao_falhar_disjuntor_da_placa(self, status, motivo):
        # A tela continua mostrando o estado real da placa; só o registro no banco falhou.
        self.janela.statusBar().showMessage(
            f"O disjuntor {status} informado pela placa não foi gravado no banco: {motivo}. "
            "Detalhes em logs/smartgrid.log.",
            self.DURACAO_AVISO_BANCO_MS,
        )

    def _avisar_rele_sem_comando(self, status_rele, momento):
        """Aviso na tela, não modal: a telemetria e a reconexão continuam enquanto ele está
        aberto. Uma mudança nova reaproveita a mesma caixa em vez de empilhar outra."""
        estado_rele = "LIGADO" if status_rele == CorteController.RELE_LIGADO else "DESLIGADO"
        texto = f"O relé de emergência passou a {estado_rele} às {momento:%H:%M:%S} sem comando do operador.\n\n"
        if status_rele == CorteController.RELE_LIGADO:
            texto += "O disjuntor foi marcado como FECHADO e a carga está ligada. Confira a bancada."
        else:
            texto += (
                "Causa provável: a placa reiniciou (cabo USB puxado ou falta de energia) e voltou com o "
                "relé desligado.\n\nO disjuntor foi marcado como ABERTO e a carga está desligada. "
                "Para ligá-la de novo, use \"Religar disjuntor\"."
            )

        if self._aviso_rele is None:
            self._aviso_rele = QMessageBox(
                QMessageBox.Warning, "Relé mudou sem comando", "", QMessageBox.Ok, self.janela
            )
            self._aviso_rele.setModal(False)
        self._aviso_rele.setText(texto)
        self._aviso_rele.show()
        self._aviso_rele.raise_()
        self.janela.statusBar().showMessage(
            f"Relé de emergência passou a {estado_rele} sem comando do operador.", self.DURACAO_AVISO_BANCO_MS
        )

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
        if not self._disjuntor_carregado:
            self.ui.label_disjuntor_status.setText("Disjuntor: lendo o estado no banco...")
            self.ui.label_disjuntor_status.setStyleSheet(
                "background-color: #7F8C8D; color: white; border-radius: 6px; padding: 6px; font-weight: bold;"
            )
            return

        dados = self.disjuntor.get_dados()
        self.ui.label_disjuntor_status.setText(dados["texto"])
        self.ui.label_disjuntor_status.setToolTip(f"Última alteração: {dados['data_hora']}")
        self.ui.label_disjuntor_status.setStyleSheet(
            f"background-color: {dados['cor']}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )
