import logging

from PySide6.QtCore import QObject, Signal

from models.evento_historico import EventoHistorico
from models.regra_alerta import RegraAlerta

logger = logging.getLogger("smartgrid")


class ComandosController(QObject):
    """Proteção local por setpoint de potência.

    O corte de emergência e o religamento ficam no CorteController, os limites de
    segurança (regras de alerta) no LimitesController e o painel serial no
    PainelSerialController. Os eventos gerados aqui são gravados no banco pelo
    EventosController.
    """

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

    setpoint_alterado = Signal(float)

    def __init__(self, janela, ui, disjuntor, historico):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.disjuntor = disjuntor
        self.historico = historico

        self.regra_setpoint = RegraAlerta(
            RegraAlerta.POTENCIA,
            self.ui.spin_setpoint.value(),
            descricao="Setpoint de potência do dashboard",
        )

        self.medicao_atual = None
        self.nivel_atual = ComandosController.NORMAL
        # Fundo da janela aplicado por último: com a telemetria chegando 10 vezes por
        # segundo, o stylesheet da janela inteira só é refeito quando o nível muda.
        self._fundo_aplicado = None

        self._conectar_sinais()
        self._aplicar_nivel(ComandosController.NORMAL)

    def _conectar_sinais(self):
        self.ui.spin_setpoint.valueChanged.connect(self._ao_alterar_setpoint)
        self.ui.slider_setpoint.valueChanged.connect(self._ao_arrastar_slider)

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
            logger.warning(
                "Limite de potência violado: %.1fW (Limite configurado: %.1fW).",
                potencia, self.regra_setpoint.limite_max,
            )
            self._registrar_evento(EventoHistorico.LIMITE_EXCEDIDO, descricao, potencia, "W")

    def reavaliar_protecao(self):
        """Atualiza o alerta depois de um corte ou religamento do disjuntor."""
        if self.medicao_atual is not None:
            self.avaliar_protecao(self.medicao_atual)
        elif not self.disjuntor.esta_fechado():
            self._aplicar_nivel(ComandosController.CARGA_DESLIGADA)

    def carga_esta_ativa(self) -> bool:
        return self.disjuntor.esta_fechado()

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
        if fundo != self._fundo_aplicado:
            self._fundo_aplicado = fundo
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
    # Histórico
    # ------------------------------------------------------------------

    def _registrar_evento(self, tipo, descricao, valor=None, unidade=""):
        """Grava o evento no banco pelo EventosController, que também o mostra na tabela."""
        self.historico.registrar(EventoHistorico(tipo, descricao, valor, unidade))
