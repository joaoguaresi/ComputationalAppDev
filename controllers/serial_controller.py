import logging
import threading

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from controllers.serial_worker import SerialWorker
from models.configuracao_serial import ConfiguracaoSerial

logger = logging.getLogger("smartgrid")


class SerialController(QObject):
    """Cria o SerialWorker numa QThread e controla o ciclo de vida dela.

    Vive na thread da interface. Os pedidos da interface (conectar, desconectar e os
    comandos do relé) entram na fila do worker e voltam na hora, sem esperar a placa.
    As respostas chegam pelos sinais daqui, que o Qt reemite na thread da interface.
    """

    # O worker confere o aviso de parar a cada 20 ms; o que mais demora no encerramento
    # é o !P, cujo ACK é esperado por até 1 s. Este tempo cobre os dois, com folga.
    TEMPO_MAXIMO_ENCERRAMENTO_MS = 3000

    estado_alterado = Signal(str, str)
    portas_listadas = Signal(list)
    conectado = Signal(str, int, bool)
    desconectado = Signal(str)
    falha_conexao = Signal(str)
    conexao_perdida = Signal(str)
    leituras_recebidas = Signal(list)
    rele_inicial = Signal(int)
    rele_confirmado = Signal(int)
    rele_nao_confirmado = Signal(int, str)
    rele_espontaneo = Signal(int, object)
    botao_pressionado = Signal(object)

    def __init__(self, parent=None, **opcoes_worker):
        """opcoes_worker vai para o SerialWorker; os testes passam uma placa simulada."""
        super().__init__(parent)
        self.estado = ConfiguracaoSerial.DESCONECTADO
        self._encerrado = False

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
        self.worker.conexao_perdida.connect(self.conexao_perdida)
        self.worker.leituras_recebidas.connect(self.leituras_recebidas)
        self.worker.rele_inicial.connect(self.rele_inicial)
        self.worker.rele_confirmado.connect(self.rele_confirmado)
        self.worker.rele_nao_confirmado.connect(self.rele_nao_confirmado)
        self.worker.rele_espontaneo.connect(self.rele_espontaneo)
        self.worker.botao_pressionado.connect(self.botao_pressionado)
        # O worker vive na thread serial: o deleteLater dele é atendido quando ela termina.
        self.thread_serial.finished.connect(self.worker.deleteLater)

    def _guardar_estado(self, estado, _detalhe):
        self.estado = estado

    def iniciar(self):
        self.thread_serial.start()
        logger.info("Thread serial iniciada; a interface roda na thread %d.", threading.get_ident())

    def conectar(self, porta, taxa, timeout_ms):
        """Pede a conexão; o andamento vem por estado_alterado e o resultado por conectado ou falha_conexao."""
        if not self._encerrado:
            self.worker.pedir_conexao(porta, taxa, timeout_ms)

    def desconectar(self):
        if not self._encerrado:
            self.worker.pedir_desconexao()

    def enviar_comando_rele(self, status_rele):
        """Pede o !1 (1) ou o !0 (0) à placa; a resposta vem por rele_confirmado ou rele_nao_confirmado.

        Sem conexão, o pedido é recusado na hora: o corte e o religamento só valem com a
        placa confirmando.
        """
        if self._encerrado or not self.esta_conectado():
            self.rele_nao_confirmado.emit(status_rele, "a placa não está conectada")
            return
        self.worker.pedir_rele(status_rele)

    def esta_conectado(self) -> bool:
        return self.estado == ConfiguracaoSerial.CONECTADO

    def encerrar(self):
        """Encerramento cooperativo: parar, quit, wait e deleteLater.

        parar() só liga o aviso; o próprio worker termina o laço, manda o !P se a placa
        estiver conectada, fecha a porta e chama quit(). Aqui o wait() espera a thread
        acabar. Não usa QThread.terminate(), que mataria a thread no meio de uma escrita
        na porta.

        Chamado pelo aboutToQuit antes do encerramento do banco: o último lote de
        leituras e o evento da desconexão, que o worker emitiu ao sair, ainda são
        entregues aqui e chegam ao DatabaseWorker antes de ele fechar.
        """
        if self._encerrado:
            return
        self._encerrado = True
        if not self.thread_serial.isRunning():
            self.thread_serial.deleteLater()
            return

        self.worker.parar()
        if not self.thread_serial.wait(self.TEMPO_MAXIMO_ENCERRAMENTO_MS):
            # Por exemplo, a abertura de uma porta Bluetooth que não responde: o Windows
            # não devolve o controle, e a thread não chega a conferir o aviso de parar.
            logger.error(
                "A thread serial não terminou em %d ms após o pedido de encerramento.",
                self.TEMPO_MAXIMO_ENCERRAMENTO_MS,
            )
            return

        # Os sinais que o worker emitiu ao sair estão na fila deste objeto, e o laço de
        # eventos da interface já parou (estamos no aboutToQuit): entrega agora.
        QCoreApplication.sendPostedEvents(self)
        # A QThread vive na thread da interface. Como no BancoController, o deleteLater
        # vai depois do wait(), e o Qt ainda o atende ao fechar a aplicação.
        self.thread_serial.deleteLater()
        logger.info("Thread serial encerrada.")
