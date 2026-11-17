import logging
import threading

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
    encerramento_solicitado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._encerrado = False

        # O nome não é "thread" para não esconder o método QObject.thread().
        self.thread_banco = QThread()
        self.thread_banco.setObjectName("DatabaseWorker")
        self.worker = DatabaseWorker()
        self.worker.moveToThread(self.thread_banco)

        self.thread_banco.started.connect(self.worker.abrir)
        self.gravacao_solicitada.connect(self.worker.gravar_leituras)
        self.encerramento_solicitado.connect(self.worker.encerrar)
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
