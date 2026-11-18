import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMessageBox

from models.dispositivo import Dispositivo
from models.evento_historico import EventoHistorico

logger = logging.getLogger("smartgrid")


class CorteController(QObject):
    """Corte de emergência (RELAY_OFF) e religamento do disjuntor.

    A operação segue a ordem do hardware:

    1. o operador confirma no QMessageBox e o controller pede o comando à placa pelo
       sinal comando_rele_solicitado (0 = desligar o relé, 1 = ligar);
    2. a placa confirma (ACK e STATUS_RELE no valor pedido) e chama confirmar_rele();
       se ela não confirmar no prazo, recusar_rele() avisa o operador e nada é gravado;
    3. só então o DatabaseWorker grava, numa única transação, o status do relé e do
       disjuntor e os eventos do histórico;
    4. só depois do COMMIT a tela muda.

    O MainWindowController liga o pedido ao SerialController: a thread serial envia o
    !0 ou o !1 e responde com rele_confirmado (ligado ao confirmar_rele) ou
    rele_nao_confirmado (ligado ao recusar_rele). Sem placa conectada, a recusa é na hora.

    Para demonstrar o ROLLBACK, o atalho Ctrl+Shift+F liga uma falha simulada que
    interrompe a gravação do corte entre a atualização do disjuntor e o registro do evento.
    """

    COMANDO_RELAY_OFF = "RELAY_OFF"
    ATALHO_FALHA_SIMULADA = "Ctrl+Shift+F"

    # STATUS_RELE do firmware: 0 = relé desligado (carga cortada), 1 = relé ligado.
    RELE_DESLIGADO = 0
    RELE_LIGADO = 1

    estado_disjuntor_alterado = Signal()
    comando_rele_solicitado = Signal(int)

    def __init__(self, janela, ui, disjuntor, historico, banco, obter_potencia_atual):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.disjuntor = disjuntor
        self.historico = historico
        self.banco = banco
        self.obter_potencia_atual = obter_potencia_atual

        # Comando pedido à placa e ainda não gravado (None quando não há nenhum).
        self._status_pendente = None
        self._potencia_no_pedido = None

        self.falha_simulada_ativa = False
        self.titulo_janela = janela.windowTitle()
        self.atalho_falha_simulada = QShortcut(QKeySequence(self.ATALHO_FALHA_SIMULADA), janela)
        self.atalho_falha_simulada.activated.connect(self._alternar_falha_simulada)

        self.ui.btn_corte_emergencia.clicked.connect(self._ao_solicitar_corte)
        self.ui.btn_religar_disjuntor.clicked.connect(self._ao_solicitar_religamento)
        self.banco.operacao_rele_gravada.connect(self._ao_gravar_operacao)
        self.banco.operacao_rele_falhou.connect(self._ao_falhar_operacao)
        self._atualizar_botoes()

    # ------------------------------------------------------------------
    # Pedido do comando à placa
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
        if resposta == QMessageBox.Yes:
            self.solicitar_corte()

    def solicitar_corte(self):
        """Pede o RELAY_OFF à placa. Separado da confirmação na tela para servir também
        ao disparo local pelo botão da bancada, que não pergunta nada."""
        self._pedir_comando(self.RELE_DESLIGADO)

    def _ao_solicitar_religamento(self):
        resposta = QMessageBox.question(
            self.janela,
            "Confirmar religamento",
            "Fechar o disjuntor e restabelecer a carga?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            self._pedir_comando(self.RELE_LIGADO)

    def _pedir_comando(self, status_rele):
        if self._status_pendente is not None:
            logger.warning("Comando do relé ignorado: a placa ainda não confirmou o comando anterior.")
            return

        self._status_pendente = status_rele
        self._potencia_no_pedido = self.obter_potencia_atual()
        self._atualizar_botoes()
        self.janela.statusBar().showMessage("Comando enviado à placa. Aguardando confirmação...")
        logger.info(
            "Comando de %s o relé enviado à placa; aguardando confirmação.",
            "desligar" if status_rele == self.RELE_DESLIGADO else "ligar",
        )
        self.comando_rele_solicitado.emit(status_rele)

    def confirmar_rele(self, status_rele):
        """A placa confirmou o comando (ACK e STATUS_RELE): só agora a operação vai para o banco."""
        if status_rele != self._status_pendente:
            logger.warning(
                "Confirmação do relé ignorada: STATUS_RELE %d não corresponde ao comando pendente.", status_rele
            )
            return

        if status_rele == self.RELE_DESLIGADO:
            eventos = [
                EventoHistorico(
                    EventoHistorico.CORTE_EMERGENCIA,
                    f"Comando {self.COMANDO_RELAY_OFF} enviado pelo operador e confirmado pela placa",
                    self._potencia_no_pedido,
                    "W",
                    dispositivo_tag=Dispositivo.TAG_RELE_EMERGENCIA,
                ),
                EventoHistorico(
                    EventoHistorico.MUDANCA_DISJUNTOR,
                    "Disjuntor aberto - proteção ativada",
                    dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
                ),
            ]
            self.banco.gravar_operacao_rele(Dispositivo.ABERTO, eventos, self.falha_simulada_ativa)
            return

        evento = EventoHistorico(
            EventoHistorico.MUDANCA_DISJUNTOR,
            "Disjuntor fechado - operação normal restabelecida",
            dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
        )
        self.banco.gravar_operacao_rele(Dispositivo.FECHADO, [evento])

    def recusar_rele(self, status_rele, motivo):
        """A placa não confirmou o comando (RastreadorRele.EXPIRADO): nada é gravado."""
        if status_rele != self._status_pendente:
            return
        self._status_pendente = None
        self._atualizar_botoes()
        self.janela.statusBar().clearMessage()

        operacao = "corte emergencial" if status_rele == self.RELE_DESLIGADO else "religamento do disjuntor"
        logger.warning("A placa não confirmou o comando de %s: %s. Nada foi gravado no banco.", operacao, motivo)
        QMessageBox.warning(
            self.janela,
            "Comando não confirmado",
            f"A placa não confirmou o comando de {operacao}.\n\n"
            f"Motivo: {motivo}\n\n"
            "Nenhuma alteração foi gravada no banco.",
        )

    # ------------------------------------------------------------------
    # Respostas do DatabaseWorker
    # ------------------------------------------------------------------

    def _ao_gravar_operacao(self, status, eventos):
        """Depois do COMMIT: atualiza o disjuntor, mostra os eventos e libera os botões."""
        self._status_pendente = None
        self.janela.statusBar().clearMessage()

        if status == Dispositivo.ABERTO:
            self.disjuntor.abrir()
            self._concluir_operacao(eventos)
            logger.warning(
                "Corte de emergência executado: comando %s confirmado pela placa com %.2f W de carga. "
                "Relé de emergência e disjuntor abertos.",
                self.COMANDO_RELAY_OFF, self._potencia_no_pedido,
            )
            QMessageBox.information(
                self.janela,
                "Corte de emergência",
                f"Comando {self.COMANDO_RELAY_OFF} confirmado pela placa.\n"
                "Disjuntor aberto e carga desligada. Ocorrência gravada no histórico.",
            )
            return

        self.disjuntor.fechar()
        self._concluir_operacao(eventos)
        logger.info("Religamento executado: relé de emergência e disjuntor fechados pelo operador.")

    def _ao_falhar_operacao(self, status, motivo, estado_no_banco):
        self._status_pendente = None
        self.janela.statusBar().clearMessage()
        self._atualizar_botoes()

        operacao = "corte emergencial" if status == Dispositivo.ABERTO else "religamento do disjuntor"
        self._informar_falha(operacao, motivo, estado_no_banco)

    def _concluir_operacao(self, eventos):
        """Mostra os eventos já gravados na transação e atualiza o dashboard."""
        for evento in eventos:
            self.historico.publicar(evento)
        self._atualizar_botoes()
        self.estado_disjuntor_alterado.emit()

    def _informar_falha(self, operacao, motivo, estado_no_banco):
        """Registra a falha no log e avisa o operador, mostrando o estado do disjuntor
        relido do banco depois do ROLLBACK."""
        logger.error("Falha na operação de %s. Rollback executado: %s.", operacao, motivo)
        logger.info("Estado do disjuntor no banco após o rollback: %s.", estado_no_banco)

        QMessageBox.critical(
            self.janela,
            f"Falha no {operacao}",
            f"O {operacao} não foi concluído.\n\n"
            f"Motivo: {motivo}\n\n"
            "A transação foi desfeita (ROLLBACK) e nenhuma alteração foi gravada no banco.\n"
            f"Estado do disjuntor no banco: {estado_no_banco}",
        )

    def _atualizar_botoes(self):
        """Com um comando aguardando a placa, os dois botões ficam bloqueados."""
        livre = self._status_pendente is None
        fechado = self.disjuntor.esta_fechado()
        self.ui.btn_corte_emergencia.setEnabled(livre and fechado)
        self.ui.btn_religar_disjuntor.setEnabled(livre and not fechado)

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
