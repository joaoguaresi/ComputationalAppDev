import logging
import sqlite3

from PySide6.QtWidgets import QDialog, QMessageBox

from controllers.regras_alerta_controller import RegrasAlertaController
from models.evento_historico import EventoHistorico
from models.limite import Limite
from models.limite_repository import LimiteRepository

logger = logging.getLogger("smartgrid")


class LimitesController:
    """Monitora a telemetria do dashboard contra os limites de segurança da tabela limites.

    Ao abrir o dashboard, carrega os limites gravados no banco e passa a comparar cada
    nova medição com eles. Quando um limite começa a ser violado (transição normal ->
    violado), acende o alarme visual no indicador da grandeza, registra o WARNING no log
    e grava o evento no histórico. Enquanto a violação continua, nada é registrado de
    novo; quando a medição volta ao normal, o alarme apaga e a próxima violação volta a
    ser registrada.

    O botão "Configurar Regras de Alerta" também fica aqui: o QDialog grava os limites
    no banco e, quando é aceito, eles passam a ser monitorados na hora.
    """

    COR_ALARME = "#C0392B"

    def __init__(self, janela, ui, historico):
        self.janela = janela
        self.ui = ui
        self.historico = historico

        # Indicador (LCD) e título de cada grandeza monitorada, com o texto e o estilo
        # originais do título para restaurar quando o alarme apagar.
        self.indicadores = {
            Limite.CORRENTE_MAX: (ui.lcd_corrente, ui.label_corrente_titulo),
            Limite.TENSAO_DESARME: (ui.lcd_tensao, ui.label_tensao_titulo),
        }
        self._titulos_originais = {
            parametro: (titulo.text(), titulo.styleSheet())
            for parametro, (_, titulo) in self.indicadores.items()
        }

        self.limites = self._carregar_limites()
        self.medicao_atual = None
        self._violados = set()

        self.ui.btn_regras_alerta.clicked.connect(self._ao_abrir_regras_alerta)

    def _carregar_limites(self) -> list:
        """Limites gravados no banco, monitorados desde a abertura do dashboard."""
        try:
            limites = LimiteRepository.listar_todos()
        except sqlite3.Error as erro:
            logger.error("Falha ao carregar os limites de segurança do banco: %s", erro)
            QMessageBox.warning(
                self.janela,
                "Limites de segurança",
                "Não foi possível carregar os limites gravados no banco, e o monitoramento "
                "começa sem limites.\nOs detalhes do erro estão em logs/smartgrid.log.",
            )
            return []

        logger.info("Monitoramento iniciado com %d limite(s) de segurança do banco.", len(limites))
        return limites

    # ------------------------------------------------------------------
    # Monitoramento da telemetria
    # ------------------------------------------------------------------

    def avaliar(self, medicao):
        """Compara a medição com cada limite e registra a violação só quando ela começa."""
        self.medicao_atual = medicao

        for limite in self.limites:
            valor = limite.extrair_valor(medicao)

            if not limite.foi_violado(valor):
                if limite.parametro in self._violados:
                    self._violados.discard(limite.parametro)
                    self._apagar_alarme(limite.parametro)
                continue

            # Continua violado: o alarme já está aceso e a violação já foi registrada.
            if limite.parametro in self._violados:
                continue

            self._violados.add(limite.parametro)
            self._acionar_alarme(limite)
            self._registrar_violacao(limite, valor)

    def aplicar_limites(self, limites):
        """Passa a monitorar os limites que acabaram de ser salvos no QDialog."""
        for parametro in self._violados:
            self._apagar_alarme(parametro)
        self._violados.clear()

        self.limites = list(limites)
        if self.medicao_atual is not None:
            self.avaliar(self.medicao_atual)

    def _registrar_violacao(self, limite, valor):
        """Registra a violação no log (WARNING) e no histórico.

        O EventosController grava o evento com EventoRepository.inserir e só depois emite
        evento_registrado, que acrescenta a linha na tabela do dashboard.
        """
        logger.warning(
            "Limite de %s violado: %.1f%s (Limite configurado: %.1f%s).",
            limite.get_grandeza(), valor, limite.unidade, limite.valor, limite.unidade,
        )
        self.historico.registrar(EventoHistorico(
            EventoHistorico.LIMITE_EXCEDIDO,
            f"Limite de {limite.get_grandeza()} violado (limite configurado: {limite.get_valor_formatado()})",
            valor,
            limite.unidade,
            dispositivo_tag=limite.dispositivo_tag,
        ))

    # ------------------------------------------------------------------
    # Alarme visual
    # ------------------------------------------------------------------

    def _acionar_alarme(self, limite):
        """Pinta de vermelho o indicador da grandeza violada e mostra o limite no título."""
        lcd, titulo = self.indicadores[limite.parametro]
        texto_original, _ = self._titulos_originais[limite.parametro]

        lcd.setStyleSheet(f"background-color: {self.COR_ALARME}; color: white; border-radius: 6px;")
        lcd.setToolTip(f"Limite configurado: {limite.get_valor_formatado()}")
        titulo.setText(f"{texto_original} - ACIMA DO LIMITE DE {limite.get_valor_formatado()}")
        titulo.setStyleSheet(f"font-weight: bold; color: {self.COR_ALARME};")

    def _apagar_alarme(self, parametro):
        lcd, titulo = self.indicadores[parametro]
        texto_original, estilo_original = self._titulos_originais[parametro]

        lcd.setStyleSheet("")
        lcd.setToolTip("")
        titulo.setText(texto_original)
        titulo.setStyleSheet(estilo_original)

    # ------------------------------------------------------------------
    # Regras de alerta (QDialog modal)
    # ------------------------------------------------------------------

    def _ao_abrir_regras_alerta(self):
        dialog = QDialog(self.janela)
        regras_dialog = RegrasAlertaController(dialog)
        if dialog.exec() != QDialog.Accepted:
            return

        # Quando o diálogo é aceito, os limites já foram gravados no banco por ele.
        limites = regras_dialog.get_limites()
        resumo = ", ".join(f"{limite.get_nome().lower()} {limite.get_valor_formatado()}" for limite in limites)
        self.historico.registrar(
            EventoHistorico(EventoHistorico.REGRAS_ALERTA, f"Limites de segurança salvos pelo operador: {resumo}")
        )
        self.aplicar_limites(limites)
