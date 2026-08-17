from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

from controllers.regras_alerta_controller import RegrasAlertaController
from models.configuracao_serial import ConfiguracaoSerial
from models.evento_historico import EventoHistorico
from models.regra_alerta import RegraAlerta


class ComandosController(QObject):
    """Comandos do operador, proteção local por setpoint e painel serial.

    Nesta etapa o comando RELAY_OFF e a conexão serial são simulados: o corte de
    emergência age sobre o model Disjuntor e o painel serial só atualiza o status
    visual, sem comunicação real com o microcontrolador.
    """

    COMANDO_RELAY_OFF = "RELAY_OFF"
    FATOR_ATENCAO = 0.9

    NORMAL = "NORMAL"
    ATENCAO = "ATENCAO"
    CRITICO = "CRITICO"
    CARGA_DESLIGADA = "CARGA_DESLIGADA"

    # String vazia = mantém a paleta do sistema (respeita o modo escuro do Windows).
    CORES_FUNDO = {
        NORMAL: "",
        ATENCAO: "#4A3B00",
        CRITICO: "#5A1A1A",
        CARGA_DESLIGADA: "",
    }

    CORES_ALERTA = {
        NORMAL: "#2ECC71",
        ATENCAO: "#F39C12",
        CRITICO: "#C0392B",
        CARGA_DESLIGADA: "#7F8C8D",
    }

    evento_registrado = Signal(object)
    estado_disjuntor_alterado = Signal()
    setpoint_alterado = Signal(float)

    def __init__(self, janela, ui, disjuntor):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.disjuntor = disjuntor

        self.regra_setpoint = RegraAlerta(
            RegraAlerta.POTENCIA,
            self.ui.spin_setpoint.value(),
            descricao="Setpoint de potência do dashboard",
        )
        self.serial = ConfiguracaoSerial()

        self.eventos = []
        self.medicao_atual = None
        self.nivel_atual = ComandosController.NORMAL

        self.regras_adicionais = []
        self._regras_violadas = set()

        self._preencher_painel_serial()
        self._conectar_sinais()
        self._atualizar_botoes_disjuntor()
        self._atualizar_status_serial()
        self._aplicar_nivel(ComandosController.NORMAL)

    # ------------------------------------------------------------------
    # Configuração inicial
    # ------------------------------------------------------------------

    def _preencher_painel_serial(self):
        self.ui.combo_porta.addItems(ConfiguracaoSerial.listar_portas())
        for baud_rate in ConfiguracaoSerial.BAUD_RATES:
            self.ui.combo_baudrate.addItem(str(baud_rate), baud_rate)

        self.ui.spin_timeout.setValue(self.serial.timeout_ms)
        self.serial.porta = self.ui.combo_porta.currentText()
        self.serial.baud_rate = self.ui.combo_baudrate.currentData()

    def _conectar_sinais(self):
        self.ui.spin_setpoint.valueChanged.connect(self._ao_alterar_setpoint)
        self.ui.slider_setpoint.valueChanged.connect(self._ao_arrastar_slider)

        self.ui.btn_corte_emergencia.clicked.connect(self._ao_solicitar_corte)
        self.ui.btn_religar_disjuntor.clicked.connect(self._ao_solicitar_religamento)
        self.ui.btn_regras_alerta.clicked.connect(self._ao_abrir_regras_alerta)

        self.ui.combo_porta.currentTextChanged.connect(self._ao_alterar_porta)
        self.ui.combo_baudrate.currentIndexChanged.connect(self._ao_alterar_baudrate)
        self.ui.spin_timeout.valueChanged.connect(self._ao_alterar_timeout)
        self.ui.btn_conectar.clicked.connect(self._ao_conectar)
        self.ui.btn_desconectar.clicked.connect(self._ao_desconectar)

    # ------------------------------------------------------------------
    # Proteção local por setpoint
    # ------------------------------------------------------------------

    def avaliar_protecao(self, medicao):
        """Reavalia o estado da proteção a cada nova medição do dashboard."""
        self.medicao_atual = medicao
        potencia = medicao.calcular_potencia()

        if not self.disjuntor.esta_fechado():
            self._aplicar_nivel(ComandosController.CARGA_DESLIGADA)
            return

        nivel = self._classificar_potencia(potencia)
        entrou_em_alerta = nivel == ComandosController.CRITICO
        entrou_em_alerta = entrou_em_alerta and self.nivel_atual != ComandosController.CRITICO

        self._aplicar_nivel(nivel, potencia)

        if entrou_em_alerta:
            descricao = (
                f"Potência de {potencia:.2f} W ultrapassou o setpoint "
                f"de {self.regra_setpoint.limite_max:.2f} W"
            )
            self._registrar_evento(EventoHistorico.LIMITE_EXCEDIDO, descricao, potencia, "W")

        self._avaliar_regras_adicionais(medicao)

    def aplicar_regras(self, regras):
        """Recebe as regras cadastradas no QDialog de regras de alerta."""
        self.regras_adicionais = list(regras)
        self._regras_violadas.clear()
        if self.medicao_atual is not None:
            self._avaliar_regras_adicionais(self.medicao_atual)

    def _avaliar_regras_adicionais(self, medicao):
        """Registra um evento a cada travessia normal -> violada de uma regra."""
        for indice, regra in enumerate(self.regras_adicionais):
            valor = regra.extrair_valor(medicao)

            if not regra.foi_violada(valor):
                self._regras_violadas.discard(indice)
                continue
            if indice in self._regras_violadas:
                continue

            self._regras_violadas.add(indice)
            unidade = regra.get_unidade()
            descricao = (
                f"{regra.descricao}: limite de "
                f"{regra.limite_max:.2f} {unidade} ultrapassado"
            )
            self._registrar_evento(EventoHistorico.LIMITE_EXCEDIDO, descricao, valor, unidade)

    def _classificar_potencia(self, potencia) -> str:
        if self.regra_setpoint.foi_violada(potencia):
            return ComandosController.CRITICO
        limite_atencao = self.regra_setpoint.limite_max * ComandosController.FATOR_ATENCAO
        if potencia >= limite_atencao:
            return ComandosController.ATENCAO
        return ComandosController.NORMAL

    def _aplicar_nivel(self, nivel, potencia=None):
        self.nivel_atual = nivel

        fundo = ComandosController.CORES_FUNDO[nivel]
        if fundo:
            self.ui.central_widget.setStyleSheet(
                f"QWidget#central_widget {{ background-color: {fundo}; }}"
            )
        else:
            self.ui.central_widget.setStyleSheet("")

        cor = ComandosController.CORES_ALERTA[nivel]
        self.ui.label_alerta_status.setText(self._montar_texto_alerta(nivel, potencia))
        self.ui.label_alerta_status.setStyleSheet(
            f"background-color: {cor}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )

    def _montar_texto_alerta(self, nivel, potencia) -> str:
        limite = self.regra_setpoint.limite_max

        if nivel == ComandosController.CARGA_DESLIGADA:
            return "Disjuntor aberto - carga desligada (RELAY_OFF)"
        if nivel == ComandosController.CRITICO:
            return f"ALERTA: {potencia:.0f} W acima do setpoint de {limite:.0f} W"
        if nivel == ComandosController.ATENCAO:
            return f"ATENÇÃO: {potencia:.0f} W próximo do setpoint de {limite:.0f} W"
        return "Proteção: dentro do limite"

    def _ao_alterar_setpoint(self, valor):
        self.regra_setpoint.limite_max = valor

        self.ui.slider_setpoint.blockSignals(True)
        self.ui.slider_setpoint.setValue(int(round(valor)))
        self.ui.slider_setpoint.blockSignals(False)

        self.setpoint_alterado.emit(valor)

        if self.medicao_atual is not None:
            self.avaliar_protecao(self.medicao_atual)

    def _ao_arrastar_slider(self, valor):
        self.ui.spin_setpoint.setValue(float(valor))

    # ------------------------------------------------------------------
    # Regras de alerta (QDialog modal)
    # ------------------------------------------------------------------

    def _ao_abrir_regras_alerta(self):
        dialog = QDialog(self.janela)
        regras_dialog = RegrasAlertaController(dialog, regras_iniciais=self.regras_adicionais)

        if dialog.exec() == QDialog.Accepted:
            self.aplicar_regras(regras_dialog.get_regras())
            self._registrar_evento(
                EventoHistorico.REGRAS_ALERTA,
                f"{len(self.regras_adicionais)} regra(s) de alerta atualizada(s) pelo operador",
            )

    # ------------------------------------------------------------------
    # Corte de emergência e religamento
    # ------------------------------------------------------------------

    def _ao_solicitar_corte(self):
        resposta = QMessageBox.question(
            self.janela,
            "Confirmar corte de emergência",
            "Enviar o comando RELAY_OFF e abrir o disjuntor?\n\n"
            "A carga será desligada imediatamente.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        potencia = self._potencia_atual()
        self.disjuntor.abrir()

        self._registrar_evento(
            EventoHistorico.CORTE_EMERGENCIA,
            f"Comando {ComandosController.COMANDO_RELAY_OFF} enviado pelo operador",
            potencia,
            "W",
        )
        self._registrar_evento(
            EventoHistorico.MUDANCA_DISJUNTOR,
            "Disjuntor aberto - proteção ativada",
        )

        self._concluir_mudanca_disjuntor()

        QMessageBox.information(
            self.janela,
            "Corte de emergência",
            f"Comando {ComandosController.COMANDO_RELAY_OFF} enviado (simulado).\n"
            "Disjuntor aberto e carga desligada.",
        )

    def _ao_solicitar_religamento(self):
        resposta = QMessageBox.question(
            self.janela,
            "Confirmar religamento",
            "Fechar o disjuntor e restabelecer a carga?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        self.disjuntor.fechar()
        self._registrar_evento(
            EventoHistorico.MUDANCA_DISJUNTOR,
            "Disjuntor fechado - operação normal restabelecida",
        )
        self._concluir_mudanca_disjuntor()

    def _concluir_mudanca_disjuntor(self):
        self._atualizar_botoes_disjuntor()
        self.estado_disjuntor_alterado.emit()

        if self.medicao_atual is not None:
            self.avaliar_protecao(self.medicao_atual)
        elif not self.disjuntor.esta_fechado():
            self._aplicar_nivel(ComandosController.CARGA_DESLIGADA)

    def _atualizar_botoes_disjuntor(self):
        fechado = self.disjuntor.esta_fechado()
        self.ui.btn_corte_emergencia.setEnabled(fechado)
        self.ui.btn_religar_disjuntor.setEnabled(not fechado)

    def _potencia_atual(self) -> float:
        if self.medicao_atual is None:
            return 0.0
        return self.medicao_atual.calcular_potencia()

    def carga_esta_ativa(self) -> bool:
        return self.disjuntor.esta_fechado()

    # ------------------------------------------------------------------
    # Painel serial (somente visual nesta etapa)
    # ------------------------------------------------------------------

    def _ao_alterar_porta(self, porta):
        self.serial.porta = porta

    def _ao_alterar_baudrate(self, indice):
        self.serial.baud_rate = self.ui.combo_baudrate.itemData(indice)

    def _ao_alterar_timeout(self, valor):
        self.serial.timeout_ms = valor

    def _ao_conectar(self):
        if not self.serial.conectar():
            QMessageBox.warning(
                self.janela,
                "Configuração inválida",
                "Verifique a porta COM, o baud rate e o timeout antes de conectar.",
            )
            return

        self._atualizar_status_serial()
        self._registrar_evento(
            EventoHistorico.CONEXAO_SERIAL,
            f"Conexão simulada aberta em {self.serial.porta} "
            f"({self.serial.baud_rate} bps, timeout {self.serial.timeout_ms} ms)",
        )

    def _ao_desconectar(self):
        self.serial.desconectar()
        self._atualizar_status_serial()
        self._registrar_evento(
            EventoHistorico.CONEXAO_SERIAL, "Conexão simulada encerrada pelo operador"
        )

    def _atualizar_status_serial(self):
        dados = self.serial.get_dados()
        conectado = self.serial.esta_conectado()

        self.ui.label_serial_status.setText(dados["texto"])
        self.ui.label_serial_status.setStyleSheet(
            f"background-color: {dados['cor']}; color: white; "
            "border-radius: 6px; padding: 6px; font-weight: bold;"
        )

        self.ui.btn_conectar.setEnabled(not conectado)
        self.ui.btn_desconectar.setEnabled(conectado)
        self.ui.combo_porta.setEnabled(not conectado)
        self.ui.combo_baudrate.setEnabled(not conectado)
        self.ui.spin_timeout.setEnabled(not conectado)

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------

    def _registrar_evento(self, tipo, descricao, valor=None, unidade=""):
        evento = EventoHistorico(tipo, descricao, valor, unidade)
        self.eventos.append(evento)
        self.evento_registrado.emit(evento)
        return evento

    def get_eventos(self) -> list:
        return list(self.eventos)
