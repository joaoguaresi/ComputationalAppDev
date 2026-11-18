import logging

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from models.config_manager import ConfigManager
from models.configuracao_serial import ConfiguracaoSerial
from models.evento_historico import EventoHistorico

logger = logging.getLogger("smartgrid")


class PainelSerialController(QObject):
    """Painel "Configuração da Conexão Serial": porta, taxa, timeout e os botões.

    Não fala com a porta: pede a conexão ao SerialController e mostra o estado que a
    thread serial informa. A porta sempre abre em 9600 bps; a taxa escolhida aqui é a
    pedida à placa no handshake (115200 por padrão). A lista de portas também vem da
    thread serial, que a atualiza a cada 2 s enquanto está desconectada: o Arduino
    aparece sozinho quando é plugado.

    Desconectar também cancela um handshake ou uma reconexão em andamento.
    """

    DURACAO_AVISO_MS = 10000

    def __init__(self, janela, ui, serial, historico):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.serial = serial
        self.historico = historico
        self.config = ConfiguracaoSerial(ConfigManager.get("porta_com"), ConfigManager.get("baud_rate"))

        self._preencher_taxas()
        self.ui.spin_timeout.setValue(self.config.timeout_ms)
        self._conectar_sinais()
        self._atualizar_painel()

    def _preencher_taxas(self):
        for taxa in ConfiguracaoSerial.BAUD_RATES:
            texto = f"{taxa} (padrão)" if taxa == ConfiguracaoSerial.BAUD_RATE_PADRAO else str(taxa)
            self.ui.combo_baudrate.addItem(texto, taxa)
        # O ConfigManager já garante que a taxa salva é uma das quatro.
        self.ui.combo_baudrate.setCurrentIndex(max(self.ui.combo_baudrate.findData(self.config.baud_rate), 0))
        self.config.baud_rate = self.ui.combo_baudrate.currentData()

    def _conectar_sinais(self):
        self.ui.combo_porta.currentIndexChanged.connect(self._ao_escolher_porta)
        self.ui.combo_baudrate.currentIndexChanged.connect(self._ao_escolher_taxa)
        self.ui.spin_timeout.valueChanged.connect(self._ao_alterar_timeout)
        self.ui.btn_conectar.clicked.connect(self._ao_conectar)
        self.ui.btn_desconectar.clicked.connect(self._ao_desconectar)

        self.serial.portas_listadas.connect(self._atualizar_portas)
        self.serial.estado_alterado.connect(self._ao_mudar_estado)
        self.serial.conectado.connect(self._ao_conectar_placa)
        self.serial.desconectado.connect(self._ao_desconectar_placa)
        self.serial.falha_conexao.connect(self._ao_falhar_conexao)
        self.serial.conexao_perdida.connect(self._ao_perder_conexao)

    # ------------------------------------------------------------------
    # Escolhas do operador
    # ------------------------------------------------------------------

    def _atualizar_portas(self, portas):
        """Lista vinda da thread serial: [(porta, descrição, parece_arduino)]."""
        combo = self.ui.combo_porta
        combo.blockSignals(True)
        combo.clear()
        for porta, descricao, _ in portas:
            combo.addItem(ConfiguracaoSerial.descrever_porta(porta, descricao), porta)

        indice = combo.findData(self.config.porta)
        if indice < 0:
            # A porta escolhida não está plugada: sugere a que parece um Arduino.
            indice = next((i for i, (_, _, arduino) in enumerate(portas) if arduino), 0)
        combo.setCurrentIndex(indice if portas else -1)
        combo.blockSignals(False)

        if combo.currentData():
            self.config.porta = combo.currentData()

    def _ao_escolher_porta(self, indice):
        porta = self.ui.combo_porta.itemData(indice)
        if porta:
            self.config.porta = porta
            ConfigManager.set("porta_com", porta)

    def _ao_escolher_taxa(self, indice):
        self.config.baud_rate = self.ui.combo_baudrate.itemData(indice)
        ConfigManager.set("baud_rate", self.config.baud_rate)

    def _ao_alterar_timeout(self, valor):
        self.config.timeout_ms = valor

    def _ao_conectar(self):
        if not self.config.validar():
            logger.warning(
                "Configuração serial inválida: porta %r, %s bps, timeout %s ms.",
                self.config.porta, self.config.baud_rate, self.config.timeout_ms,
            )
            QMessageBox.warning(
                self.janela,
                "Configuração inválida",
                "Escolha a porta do Arduino, uma das quatro taxas e um timeout entre "
                f"{ConfiguracaoSerial.TIMEOUT_MINIMO} e {ConfiguracaoSerial.TIMEOUT_MAXIMO} ms.\n\n"
                "Se o Arduino não aparece na lista, confira o cabo USB: a lista se atualiza a cada 2 s.",
            )
            return

        if ConfigManager.get("porta_com") != self.config.porta:
            ConfigManager.set("porta_com", self.config.porta)
        logger.info(
            "Conexão pedida em %s: abre em 9600 bps e pede %d bps à placa.", self.config.porta, self.config.baud_rate
        )
        self.serial.conectar(self.config.porta, self.config.baud_rate, self.config.timeout_ms)

    def _ao_desconectar(self):
        self.serial.desconectar()

    # ------------------------------------------------------------------
    # Respostas da thread serial
    # ------------------------------------------------------------------

    def _ao_mudar_estado(self, estado, detalhe):
        self.config.atualizar_estado(estado, detalhe)
        self._atualizar_painel()

    def _atualizar_painel(self):
        dados = self.config.get_dados()
        livre = self.config.esta_desconectado()

        self.ui.label_serial_status.setText(dados["texto"])
        self.ui.label_serial_status.setStyleSheet(
            f"background-color: {dados['cor']}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )
        self.ui.btn_conectar.setEnabled(livre)
        self.ui.btn_desconectar.setEnabled(not livre)
        self.ui.combo_porta.setEnabled(livre)
        self.ui.combo_baudrate.setEnabled(livre)
        self.ui.spin_timeout.setEnabled(livre)

    def _ao_conectar_placa(self, porta, taxa, reconexao):
        if reconexao:
            descricao = f"Conexão com a placa restabelecida em {porta}: handshake refeito, telemetria a {taxa} bps"
        else:
            descricao = f"Conexão aberta em {porta}: handshake em 9600 bps confirmado, telemetria a {taxa} bps"
        self._registrar(descricao)

    def _ao_desconectar_placa(self, motivo):
        self._registrar(f"Conexão com a placa {motivo}")

    def _ao_falhar_conexao(self, motivo):
        porta = self.config.porta
        self._registrar(f"Falha na conexão com a placa em {porta}: {motivo}")
        QMessageBox.warning(
            self.janela,
            "Falha na conexão",
            f"Não foi possível conectar à placa em {porta}.\n\n"
            f"Motivo: {motivo}\n\n"
            "Os detalhes estão em logs/smartgrid.log.",
        )

    def _ao_perder_conexao(self, motivo):
        # Barra de status em vez de QMessageBox: o aviso não trava a tela.
        self._registrar(f"Conexão com a placa perdida: {motivo}")
        self.janela.statusBar().showMessage(f"Conexão com a placa perdida: {motivo}.", self.DURACAO_AVISO_MS)

    def _registrar(self, descricao):
        self.historico.registrar(EventoHistorico(EventoHistorico.CONEXAO_SERIAL, descricao))
