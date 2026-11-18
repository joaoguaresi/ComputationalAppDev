import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal

from controllers.serial_worker import SerialWorker
from models.configuracao_serial import ConfiguracaoSerial

logger = logging.getLogger("smartgrid")


class SerialController(QObject):
    """Cria o SerialWorker numa QThread e controla o ciclo de vida dela.

    Vive na thread da interface. Os pedidos da interface (conectar e desconectar)
    entram na fila do worker e voltam na hora, sem esperar a placa. As respostas
    chegam pelos sinais daqui, que o Qt reemite na thread da interface.
    """

    estado_alterado = Signal(str, str)
    portas_listadas = Signal(list)
    conectado = Signal(str, int, bool)
    desconectado = Signal(str)
    falha_conexao = Signal(str)

    def __init__(self, parent=None, **opcoes_worker):
        """opcoes_worker vai para o SerialWorker; os testes passam uma placa simulada."""
        super().__init__(parent)
        self.estado = ConfiguracaoSerial.DESCONECTADO

        # O nome não é "thread" para não esconder o método QObject.thread().
        self.thread_serial = QThread()
        self.thread_serial.setObjectName("SerialWorker")
        self.worker = SerialWorker(**opcoes_worker)
        self.worker.moveToThread(self.thread_serial)

        # O started é emitido já na thread serial: o laço do worker roda nela.
        self.thread_serial.started.connect(self.worker.executar)

        # O estado é guardado antes de qualquer outro receptor ser avisado.
        self.estado_alterado.connect(self._guardar_estado)

        # Sinal ligado a sinal: o worker emite na thread serial e o Qt reemite estes na
        # thread da interface, onde ficam os controllers que atualizam a tela.
        self.worker.estado_alterado.connect(self.estado_alterado)
        self.worker.portas_listadas.connect(self.portas_listadas)
        self.worker.conectado.connect(self.conectado)
        self.worker.desconectado.connect(self.desconectado)
        self.worker.falha_conexao.connect(self.falha_conexao)

    def _guardar_estado(self, estado, _detalhe):
        self.estado = estado

    def iniciar(self):
        self.thread_serial.start()
        logger.info("Thread serial iniciada; a interface roda na thread %d.", threading.get_ident())

    def conectar(self, porta, taxa, timeout_ms):
        """Pede a conexão; o andamento vem por estado_alterado e o resultado por conectado ou falha_conexao."""
        self.worker.pedir_conexao(porta, taxa, timeout_ms)

    def desconectar(self):
        self.worker.pedir_desconexao()

    def esta_conectado(self) -> bool:
        return self.estado == ConfiguracaoSerial.CONECTADO

    def encerrar(self):
        """Pede ao worker que pare e espera a thread terminar."""
        if not self.thread_serial.isRunning():
            return
        self.worker.parar()
        self.thread_serial.wait()
