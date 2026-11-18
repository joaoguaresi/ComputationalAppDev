import logging
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal

from controllers.database_worker import DatabaseWorker

logger = logging.getLogger("smartgrid")


class BancoController(QObject):
    """Cria o DatabaseWorker numa QThread e controla o ciclo de vida dela.

    Vive na thread da interface. Para pedir trabalho ao banco, a interface emite os
    sinais daqui, ligados aos slots do worker: como o worker está em outra thread, o Qt
    entrega cada pedido pela fila de eventos dela (conexão enfileirada), e a interface
    segue sem esperar a resposta.
    """

    # Maior que o timeout de 5 s do SQLite: uma gravação que está esperando o banco
    # liberar ainda consegue terminar antes de a interface desistir de esperar.
    TEMPO_MAXIMO_ENCERRAMENTO_MS = 7000

    gravacao_solicitada = Signal(list)
    evento_solicitado = Signal(object)
    rele_espontaneo_solicitado = Signal(int, object)
    botao_local_solicitado = Signal(object)
    operacao_rele_solicitada = Signal(str, list, bool)
    consulta_solicitada = Signal(int, object)
    encerramento_solicitado = Signal()

    # Repassam as respostas do worker, já na thread da interface.
    evento_gravado = Signal(object)
    evento_nao_gravado = Signal(object, str)
    operacao_rele_gravada = Signal(str, list)
    operacao_rele_falhou = Signal(str, str, str)
    historico_consultado = Signal(int, list, int)
    historico_falhou = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._encerrado = False
        self._ultimo_pedido = 0

        # O nome não é "thread" para não esconder o método QObject.thread().
        self.thread_banco = QThread()
        self.thread_banco.setObjectName("DatabaseWorker")
        self.worker = DatabaseWorker()
        self.worker.moveToThread(self.thread_banco)

        self.thread_banco.started.connect(self.worker.abrir)
        self.gravacao_solicitada.connect(self.worker.gravar_leituras)
        self.evento_solicitado.connect(self.worker.registrar_evento)
        self.rele_espontaneo_solicitado.connect(self.worker.registrar_rele_espontaneo)
        self.botao_local_solicitado.connect(self.worker.registrar_botao_local)
        self.operacao_rele_solicitada.connect(self.worker.gravar_operacao_rele)
        self.consulta_solicitada.connect(self.worker.consultar_historico)
        self.encerramento_solicitado.connect(self.worker.encerrar)

        # Sinal ligado a sinal: o worker emite na thread do banco e o Qt reemite estes na
        # thread da interface, onde ficam os controllers que atualizam a tela.
        self.worker.evento_gravado.connect(self.evento_gravado)
        self.worker.evento_nao_gravado.connect(self.evento_nao_gravado)
        self.worker.operacao_rele_gravada.connect(self.operacao_rele_gravada)
        self.worker.operacao_rele_falhou.connect(self.operacao_rele_falhou)
        self.worker.historico_consultado.connect(self.historico_consultado)
        self.worker.historico_falhou.connect(self.historico_falhou)
        # O worker vive na thread do banco: o deleteLater dele é atendido quando ela termina.
        self.thread_banco.finished.connect(self.worker.deleteLater)

    def iniciar(self):
        self.thread_banco.start()
        logger.info("Thread do banco iniciada; a interface roda na thread %d.", threading.get_ident())

    def gravar_leituras(self, leituras):
        """Entrega um lote de LeituraTelemetria ao worker, que grava a média de cada janela.

        Volta na hora: a gravação acontece na thread do banco. A lista é copiada porque
        quem chamou pode continuar enchendo a dele enquanto o worker lê esta.
        """
        self.gravacao_solicitada.emit(list(leituras))

    def registrar_evento(self, evento):
        """Pede a gravação de um EventoHistorico; a resposta vem por evento_gravado ou
        evento_nao_gravado."""
        self.evento_solicitado.emit(evento)

    def registrar_rele_espontaneo(self, status_rele, momento=None):
        """Relé que mudou sem comando (RastreadorRele.ESPONTANEO). O momento padrão é o
        da chamada, ou seja, o da detecção."""
        self.rele_espontaneo_solicitado.emit(status_rele, momento or datetime.now())

    def registrar_botao_local(self, momento=None):
        """Aperto confirmado do botão da bancada (DetectorBotao)."""
        self.botao_local_solicitado.emit(momento or datetime.now())

    def gravar_operacao_rele(self, status, eventos, simular_falha=False):
        """Pede a gravação do corte (ABERTO) ou do religamento (FECHADO), já confirmado
        pela placa. A resposta vem por operacao_rele_gravada ou operacao_rele_falhou."""
        self.operacao_rele_solicitada.emit(status, list(eventos), simular_falha)

    def consultar_historico(self, filtro) -> int:
        """Pede a consulta do FiltroHistorico e devolve o número do pedido na hora.

        A resposta vem por historico_consultado ou historico_falhou com o mesmo número.
        Se o operador disparar várias consultas seguidas, quem pediu compara o número e
        ignora as respostas dos pedidos antigos.
        """
        self._ultimo_pedido += 1
        self.consulta_solicitada.emit(self._ultimo_pedido, filtro)
        return self._ultimo_pedido

    def encerrar(self):
        """Encerramento cooperativo: pede ao worker que pare e espera a thread terminar.

        Não usa QThread.terminate(), que mata a thread no meio do que ela estiver fazendo
        e pode deixar uma transação pela metade.
        """
        if self._encerrado or not self.thread_banco.isRunning():
            return
        self._encerrado = True

        self.encerramento_solicitado.emit()
        if not self.thread_banco.wait(self.TEMPO_MAXIMO_ENCERRAMENTO_MS):
            logger.error(
                "A thread do banco não terminou em %d ms após o pedido de encerramento.",
                self.TEMPO_MAXIMO_ENCERRAMENTO_MS,
            )
            return

        # A QThread vive na thread da interface, cujo laço de eventos já pode ter parado
        # (o encerramento é chamado pelo aboutToQuit). Um deleteLater ligado ao finished
        # chegaria enfileirado e nunca seria atendido; chamado aqui, depois do wait(), o
        # Qt ainda o atende ao fechar a aplicação.
        self.thread_banco.deleteLater()
