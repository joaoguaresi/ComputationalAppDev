import logging
import queue
import threading
import time

import serial
from PySide6.QtCore import QObject, Signal, Slot

from models.configuracao_serial import ConfiguracaoSerial
from models.protocolo import TAXA_INICIAL

logger = logging.getLogger("smartgrid")

# Estados da máquina (ConfiguracaoSerial), com nomes curtos para as transições.
DESCONECTADO = ConfiguracaoSerial.DESCONECTADO
CONECTANDO = ConfiguracaoSerial.CONECTANDO
NEGOCIANDO = ConfiguracaoSerial.NEGOCIANDO
CALIBRANDO = ConfiguracaoSerial.CALIBRANDO
CONECTADO = ConfiguracaoSerial.CONECTADO
RECONECTANDO = ConfiguracaoSerial.RECONECTANDO
DESCONECTANDO = ConfiguracaoSerial.DESCONECTANDO


class FalhaConexaoError(Exception):
    """A conexão não foi estabelecida: porta que não abre ou placa que não responde."""


class ConexaoInterrompidaError(Exception):
    """O operador pediu para desconectar, ou a aplicação está fechando, no meio de uma espera."""


def abrir_porta_serial(porta):
    """Abre a porta de verdade, sempre em 9600 bps, a taxa em que a placa liga.

    Abrir a porta mexe no DTR, e o Arduino Uno reinicia: é por isso que a placa manda
    o banner logo depois. Os testes trocam esta função por uma placa simulada.
    """
    return serial.Serial(
        porta,
        TAXA_INICIAL,
        timeout=SerialWorker.TIMEOUT_LEITURA_S,
        write_timeout=SerialWorker.TIMEOUT_ESCRITA_S,
    )


class SerialWorker(QObject):
    """Comunicação com a placa fora da thread da interface.

    O SerialController move o worker para uma QThread (moveToThread) e liga o started
    dela ao executar(). O executar() é um laço que ocupa a thread do começo ao fim: a
    cada volta ele atende a fila de comandos, lê o que chegou na porta e avança a
    máquina de estados. Tudo o que bloqueia (abrir a porta, ler e escrever) acontece
    aqui, nunca na thread da interface.

    Fila de comandos: como o laço não devolve o controle ao Qt, um slot chamado por
    sinal enfileirado só rodaria depois do fim da thread. Por isso a interface faz os
    pedidos pelos métodos pedir_*, que só colocam o pedido numa queue.Queue (segura
    entre threads) e voltam na hora; o laço atende a fila na ordem de chegada. As
    respostas saem por sinais, que o Qt entrega na thread da interface.

    Máquina de estados (constantes em ConfiguracaoSerial):

        DESCONECTADO --conectar--> CONECTANDO --banner--> NEGOCIANDO --ACK--> CALIBRANDO --> CONECTADO
        CONECTADO --cabo puxado ou silêncio--> RECONECTANDO --porta voltou--> CONECTANDO
        qualquer estado --desconectar--> DESCONECTANDO --> DESCONECTADO

    Encerramento cooperativo: parar() só liga um aviso (threading.Event), que o laço e
    as esperas conferem a cada volta. A thread nunca é morta no meio de uma leitura ou
    escrita.
    """

    # Espera máxima de cada leitura da porta: mesmo sem nada chegando, o laço volta a
    # atender a fila pelo menos nesse intervalo.
    TIMEOUT_LEITURA_S = 0.02
    TIMEOUT_ESCRITA_S = 0.5
    # Espera da fila quando não há porta aberta.
    ESPERA_FILA_S = 0.2
    # De quanto em quanto tempo a lista de portas do painel é atualizada.
    INTERVALO_PORTAS_S = 2.0

    _CONECTAR = "CONECTAR"
    _DESCONECTAR = "DESCONECTAR"

    estado_alterado = Signal(str, str)  # estado e detalhe para o painel
    portas_listadas = Signal(list)
    conectado = Signal(str, int, bool)  # porta, taxa e se foi uma reconexão automática
    desconectado = Signal(str)          # motivo
    falha_conexao = Signal(str)         # motivo

    def __init__(self, abrir_porta=abrir_porta_serial, listar_portas=ConfiguracaoSerial.listar_portas):
        # Sem pai: o moveToThread não aceita um objeto que tem pai.
        super().__init__()
        self._abrir_porta = abrir_porta
        self._listar_portas = listar_portas

        self._fila = queue.Queue()
        self._parar = threading.Event()
        self._cancelar = threading.Event()

        self.estado = DESCONECTADO
        self._porta = None
        self._nome_porta = ""
        self._taxa = None
        self._timeout_resposta_s = ConfiguracaoSerial.TIMEOUT_PADRAO / 1000

        self._portas = None
        self._proxima_listagem = 0.0

    # ------------------------------------------------------------------
    # Pedidos da interface (chamados na thread da interface)
    # ------------------------------------------------------------------

    def pedir_conexao(self, porta, taxa, timeout_ms):
        """Pede a conexão: a porta abre em 9600 e a placa é levada para a taxa escolhida."""
        self._fila.put((self._CONECTAR, porta, taxa, timeout_ms))

    def pedir_desconexao(self):
        """Pede a desconexão. Também interrompe um handshake em andamento."""
        self._cancelar.set()
        self._fila.put((self._DESCONECTAR,))

    def parar(self):
        """Encerramento cooperativo: o laço termina na próxima volta."""
        self._parar.set()

    # ------------------------------------------------------------------
    # Laço da thread serial
    # ------------------------------------------------------------------

    @Slot()
    def executar(self):
        """Laço da thread serial. Ligado ao started da QThread, roda até parar()."""
        logger.info("SerialWorker iniciado na thread %d.", threading.get_ident())
        self._mudar_estado(DESCONECTADO)
        while not self._parar.is_set():
            if self.estado == DESCONECTADO:
                self._ciclo_desconectado()
            else:
                self._ciclo_conectado()
        self._finalizar()

    def _ciclo_desconectado(self):
        """Sem porta aberta: espera um pedido e mantém a lista de portas do painel em dia."""
        self._atualizar_portas()
        try:
            comando = self._fila.get(timeout=self.ESPERA_FILA_S)
        except queue.Empty:
            return
        self._atender(comando)

    def _ciclo_conectado(self):
        """Com a porta aberta: atende os pedidos que chegaram."""
        self._atender_fila()
        self._parar.wait(self.TIMEOUT_LEITURA_S)

    def _atender_fila(self):
        """Atende, sem esperar, todos os pedidos que já estão na fila."""
        while True:
            try:
                comando = self._fila.get_nowait()
            except queue.Empty:
                return
            self._atender(comando)

    def _atender(self, comando):
        tipo = comando[0]
        if tipo == self._CONECTAR:
            self._conectar(*comando[1:])
        elif tipo == self._DESCONECTAR:
            self._cancelar.clear()
            if self.estado != DESCONECTADO:
                self._desconectar("pelo operador")

    def _interrompido(self) -> bool:
        return self._parar.is_set() or self._cancelar.is_set()

    def _mudar_estado(self, estado, detalhe=""):
        self.estado = estado
        self.estado_alterado.emit(estado, detalhe)

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------

    def _conectar(self, porta, taxa, timeout_ms):
        if self.estado != DESCONECTADO:
            logger.warning("Pedido de conexão ignorado: a conexão já está em %s.", self.estado)
            return
        if self._cancelar.is_set():
            # Um Desconectar que veio depois deste pedido já o cancelou.
            return

        self._nome_porta = porta
        self._taxa = taxa
        self._timeout_resposta_s = timeout_ms / 1000

        try:
            self._abrir()
        except FalhaConexaoError as erro:
            self._fechar_porta()
            logger.error("Falha ao conectar na placa em %s: %s.", porta, erro)
            self._mudar_estado(DESCONECTADO)
            self.falha_conexao.emit(str(erro))

    def _abrir(self):
        """Abre a porta em 9600 bps."""
        self._mudar_estado(CONECTANDO, f"{self._nome_porta} em {TAXA_INICIAL} bps")
        try:
            self._porta = self._abrir_porta(self._nome_porta)
        except (serial.SerialException, OSError, ValueError) as erro:
            raise FalhaConexaoError(self._explicar_erro_abertura(erro)) from erro
        logger.info("Porta %s aberta em %d bps.", self._nome_porta, TAXA_INICIAL)

    @staticmethod
    def _explicar_erro_abertura(erro) -> str:
        texto = str(erro)
        if "PermissionError" in texto or "Acesso negado" in texto or "Access is denied" in texto:
            return f"a porta está em uso por outro programa (feche o Monitor Serial da Arduino IDE) - {texto}"
        if "FileNotFoundError" in texto:
            return f"a porta não existe ou a placa foi desconectada - {texto}"
        return f"não foi possível abrir a porta - {texto}"

    def _desconectar(self, motivo):
        self._mudar_estado(DESCONECTANDO, self._nome_porta)
        self._fechar_porta()
        logger.info("Conexão com a placa em %s encerrada %s.", self._nome_porta, motivo)
        self._mudar_estado(DESCONECTADO)
        self.desconectado.emit(motivo)

    def _fechar_porta(self):
        if self._porta is None:
            return
        try:
            self._porta.close()
        except (serial.SerialException, OSError) as erro:
            # Com o cabo puxado o close também pode falhar; a porta é abandonada assim mesmo.
            logger.warning("Falha ao fechar a porta %s: %s", self._nome_porta, erro)
        self._porta = None

    def _atualizar_portas(self):
        agora = time.monotonic()
        if agora < self._proxima_listagem:
            return
        self._proxima_listagem = agora + self.INTERVALO_PORTAS_S
        try:
            portas = self._listar_portas()
        except OSError as erro:
            logger.warning("Não foi possível listar as portas seriais: %s", erro)
            return
        if portas != self._portas:
            self._portas = portas
            self.portas_listadas.emit(list(portas))

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    def _finalizar(self):
        self._fechar_porta()
        self.estado = DESCONECTADO
        logger.info("SerialWorker encerrado na thread %d.", threading.get_ident())
        # O laço rodou dentro do started da QThread. O quit() faz o exec() que vem
        # depois dele terminar na hora, e a thread acaba.
        self.thread().quit()
