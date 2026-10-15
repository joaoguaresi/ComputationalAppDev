import logging
import sqlite3
from contextlib import closing

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMessageBox

from database.connection import Database
from models.dispositivo import Dispositivo
from models.dispositivo_repository import DispositivoRepository
from models.evento_historico import EventoHistorico
from models.evento_repository import EventoRepository

logger = logging.getLogger("smartgrid")


class FalhaOperacaoError(RuntimeError):
    """Interrompe o corte ou o religamento no meio da transação. Como é lançada dentro
    do with conn:, o SQLite desfaz tudo o que já tinha sido feito (ROLLBACK)."""


class CorteController(QObject):
    """Corte de emergência (RELAY_OFF) e religamento do disjuntor.

    Cada operação grava o novo status do relé de emergência e do disjuntor e os eventos
    do histórico numa única transação: ou tudo é gravado, ou nada é. O comando RELAY_OFF
    continua simulado nesta etapa, sem comunicação real com o microcontrolador.

    Para demonstrar o ROLLBACK, o atalho Ctrl+Shift+F liga uma falha simulada que
    interrompe o corte entre a atualização do disjuntor e o registro do evento.
    """

    COMANDO_RELAY_OFF = "RELAY_OFF"
    ATALHO_FALHA_SIMULADA = "Ctrl+Shift+F"

    # O relé recebe o RELAY_OFF e o disjuntor sinaliza a proteção: os dois mudam juntos.
    TAGS_DISPOSITIVOS = (Dispositivo.TAG_RELE_EMERGENCIA, Dispositivo.TAG_DISJUNTOR_PRINCIPAL)

    estado_disjuntor_alterado = Signal()

    def __init__(self, janela, ui, disjuntor, historico, obter_potencia_atual):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.disjuntor = disjuntor
        self.historico = historico
        self.obter_potencia_atual = obter_potencia_atual

        self.falha_simulada_ativa = False
        self.titulo_janela = janela.windowTitle()
        self.atalho_falha_simulada = QShortcut(QKeySequence(self.ATALHO_FALHA_SIMULADA), janela)
        self.atalho_falha_simulada.activated.connect(self._alternar_falha_simulada)

        self.ui.btn_corte_emergencia.clicked.connect(self._ao_solicitar_corte)
        self.ui.btn_religar_disjuntor.clicked.connect(self._ao_solicitar_religamento)
        self._atualizar_botoes()

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

        potencia = self.obter_potencia_atual()
        eventos = [
            EventoHistorico(
                EventoHistorico.CORTE_EMERGENCIA,
                f"Comando {self.COMANDO_RELAY_OFF} enviado pelo operador",
                potencia,
                "W",
                dispositivo_tag=Dispositivo.TAG_RELE_EMERGENCIA,
            ),
            EventoHistorico(
                EventoHistorico.MUDANCA_DISJUNTOR,
                "Disjuntor aberto - proteção ativada",
                dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
            ),
        ]

        try:
            self._gravar_operacao(Dispositivo.ABERTO, eventos, self.falha_simulada_ativa)
        except (FalhaOperacaoError, sqlite3.Error) as erro:
            self._informar_falha("corte emergencial", erro)
            return

        # Só depois do COMMIT a tela muda: o dashboard nunca mostra um corte que não foi gravado.
        self.disjuntor.abrir()
        self._concluir_operacao(eventos)
        logger.warning(
            "Corte de emergência executado: comando %s enviado com %.2f W de carga. "
            "Relé de emergência e disjuntor abertos.",
            self.COMANDO_RELAY_OFF, potencia,
        )

        QMessageBox.information(
            self.janela,
            "Corte de emergência",
            f"Comando {self.COMANDO_RELAY_OFF} enviado (simulado).\n"
            "Disjuntor aberto e carga desligada. Ocorrência gravada no histórico.",
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

        evento = EventoHistorico(
            EventoHistorico.MUDANCA_DISJUNTOR,
            "Disjuntor fechado - operação normal restabelecida",
            dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
        )

        try:
            self._gravar_operacao(Dispositivo.FECHADO, [evento])
        except (FalhaOperacaoError, sqlite3.Error) as erro:
            self._informar_falha("religamento do disjuntor", erro)
            return

        self.disjuntor.fechar()
        self._concluir_operacao([evento])
        logger.info("Religamento executado: relé de emergência e disjuntor fechados pelo operador.")

    @classmethod
    def _gravar_operacao(cls, status, eventos, simular_falha=False):
        """Grava o novo status do relé e do disjuntor e os eventos numa única transação.

        O with conn: faz o COMMIT só se o bloco inteiro terminar sem erro. Qualquer
        exceção no meio, inclusive a falha simulada, faz o SQLite desfazer tudo
        (ROLLBACK): o status nunca muda sem o evento, nem o evento fica gravado sem o status.
        """
        with closing(Database.get_connection()) as conn:
            with conn:
                for tag in cls.TAGS_DISPOSITIVOS:
                    if not DispositivoRepository.atualizar_status(tag, status, conn=conn):
                        raise FalhaOperacaoError(f"dispositivo {tag} não está cadastrado no banco")

                if simular_falha:
                    raise FalhaOperacaoError(
                        "falha simulada entre a atualização do disjuntor e o registro do evento"
                    )

                for evento in eventos:
                    EventoRepository.inserir(evento, conn=conn)

    def _concluir_operacao(self, eventos):
        """Depois do COMMIT: mostra os eventos gravados e atualiza o dashboard."""
        for evento in eventos:
            self.historico.publicar(evento)
        self._atualizar_botoes()
        self.estado_disjuntor_alterado.emit()

    def _informar_falha(self, operacao, erro):
        """Registra a falha no log e avisa o operador, mostrando o estado do disjuntor
        relido do banco depois do ROLLBACK."""
        logger.error("Falha na operação de %s. Rollback executado: %s.", operacao, erro)
        estado = self._consultar_estado_no_banco()

        QMessageBox.critical(
            self.janela,
            f"Falha no {operacao}",
            f"O {operacao} não foi concluído.\n\n"
            f"Motivo: {erro}\n\n"
            "A transação foi desfeita (ROLLBACK) e nenhuma alteração foi gravada no banco.\n"
            f"Estado do disjuntor no banco: {estado}",
        )

    def _consultar_estado_no_banco(self) -> str:
        """Relê o status do disjuntor para comprovar que o ROLLBACK manteve o estado anterior."""
        try:
            dispositivo = DispositivoRepository.buscar_por_tag(Dispositivo.TAG_DISJUNTOR_PRINCIPAL)
        except sqlite3.Error as erro:
            logger.error("Não foi possível reler o estado do disjuntor após o rollback: %s", erro)
            return "não foi possível consultar"

        if dispositivo is None:
            return "não cadastrado"

        logger.info("Estado do disjuntor no banco após o rollback: %s.", dispositivo.status)
        return dispositivo.status

    def _atualizar_botoes(self):
        fechado = self.disjuntor.esta_fechado()
        self.ui.btn_corte_emergencia.setEnabled(fechado)
        self.ui.btn_religar_disjuntor.setEnabled(not fechado)

    # ------------------------------------------------------------------
    # Falha simulada (demonstração do ROLLBACK)
    # ------------------------------------------------------------------

    def _alternar_falha_simulada(self):
        self.falha_simulada_ativa = not self.falha_simulada_ativa

        if self.falha_simulada_ativa:
            self.janela.setWindowTitle(f"{self.titulo_janela} [TESTE: falha simulada no corte ATIVA]")
            logger.warning(
                "Falha simulada ativada: o próximo corte emergencial será interrompido "
                "antes do registro do evento."
            )
            mensagem = (
                "Falha simulada ATIVADA.\n\n"
                "O próximo corte emergencial será interrompido entre a atualização do "
                "disjuntor e o registro do evento, e o banco deve desfazer a operação (ROLLBACK).\n\n"
                f"Pressione {self.ATALHO_FALHA_SIMULADA} de novo para desativar."
            )
        else:
            self.janela.setWindowTitle(self.titulo_janela)
            logger.info("Falha simulada desativada: o corte emergencial volta a operar normalmente.")
            mensagem = "Falha simulada desativada.\n\nO corte emergencial volta a operar normalmente."

        QMessageBox.information(self.janela, "Modo de teste", mensagem)
