import logging
import sqlite3
import threading

from PySide6.QtCore import QObject, Signal, Slot

from database.connection import Database
from models.agregador_leituras import AgregadorLeituras
from models.evento_historico import EventoHistorico
from models.evento_repository import EventoRepository
from models.leitura_repository import LeituraRepository

logger = logging.getLogger("smartgrid")


class DatabaseWorker(QObject):
    """Acesso ao banco fora da thread da interface.

    O BancoController move o worker para uma QThread (moveToThread). A partir daí os
    slots dele rodam na thread do banco, um de cada vez, na ordem em que os pedidos
    chegam pela fila de eventos dessa thread. A interface nunca chama estes métodos
    diretamente, porque eles rodariam na thread dela: ela emite os sinais do
    BancoController, ligados a estes slots.

    A conexão SQLite é aberta e fechada dentro da thread do banco, porque o sqlite3 não
    deixa usar uma conexão em outra thread.
    """

    falhou = Signal(str)

    # Respostas dos pedidos de evento, entregues na thread da interface pela fila dela.
    evento_gravado = Signal(object)
    evento_nao_gravado = Signal(object, str)

    def __init__(self):
        # Sem pai: o moveToThread não aceita um objeto que tem pai.
        super().__init__()
        self._conn = None
        self._agregador = AgregadorLeituras.do_config()
        self._avisou_sem_conexao = False

    @Slot()
    def abrir(self):
        """Abre a conexão do worker. Ligado ao started da QThread, roda na thread do banco."""
        try:
            self._conn = Database.get_connection()
        except sqlite3.Error as erro:
            logger.error("DatabaseWorker: falha ao abrir a conexão com o banco: %s", erro)
            self.falhou.emit(str(erro))
            return

        logger.info(
            "DatabaseWorker iniciado: conexão aberta na thread %d, leituras gravadas em janelas de %d ms.",
            threading.get_ident(), self._agregador.taxa_ms,
        )

    @Slot(list)
    def gravar_leituras(self, leituras):
        """Recebe um lote de LeituraTelemetria e grava a média de cada janela que fechou.

        As janelas fechadas pelo lote inteiro vão para o banco numa única transação, com
        um único executemany: a 200 leituras por segundo, gravar uma a uma seria lento.
        """
        janelas = []
        for leitura in leituras:
            janelas.extend(self._agregador.adicionar(leitura))
        self._gravar_janelas(janelas)

    @Slot(object)
    def registrar_evento(self, evento):
        """Grava um EventoHistorico e avisa a interface com evento_gravado.

        A tabela do dashboard só ganha a linha quando esse sinal chega: ela mostra apenas
        o que está gravado no banco. Se a gravação falhar, o evento volta pelo
        evento_nao_gravado com o motivo.
        """
        if self._conn is None:
            logger.error("Evento '%s' não gravado: a conexão do DatabaseWorker não está aberta.", evento.tipo)
            self.evento_nao_gravado.emit(evento, "a conexão com o banco não está aberta")
            return

        try:
            with self._conn:
                EventoRepository.inserir(evento, conn=self._conn)
        except sqlite3.Error as erro:
            logger.error("Falha ao gravar o evento '%s' no histórico. Rollback executado: %s.", evento.tipo, erro)
            self.evento_nao_gravado.emit(evento, str(erro))
            return

        self.evento_gravado.emit(evento)

    @Slot(int, object)
    def registrar_rele_espontaneo(self, status_rele, momento):
        """Relé que mudou sem comando do operador (RastreadorRele.ESPONTANEO).

        É uma anomalia de hardware: vai para o log como WARNING e para o histórico. O
        momento é o da detecção, não o da gravação, que pode vir alguns milissegundos depois.
        """
        logger.warning("Relé de emergência mudou sem comando do operador: STATUS_RELE = %d.", status_rele)
        self.registrar_evento(EventoHistorico.rele_espontaneo(status_rele, momento))

    @Slot(object)
    def registrar_botao_local(self, momento):
        """Aperto confirmado do botão da bancada (DetectorBotao), o disparo local do disjuntor."""
        logger.warning("Botão local da bancada pressionado: disparo do disjuntor solicitado.")
        self.registrar_evento(EventoHistorico.botao_local(momento))

    @Slot()
    def encerrar(self):
        """Grava a janela incompleta, fecha a conexão e termina o laço de eventos da thread.

        O pedido chega pela fila depois dos que já estavam nela: os lotes pendentes são
        gravados antes, e nada é interrompido no meio de uma transação.
        """
        ultima = self._agregador.finalizar()
        self._gravar_janelas(ultima)

        if self._conn is not None:
            self._conn.close()
            self._conn = None

        logger.info(
            "DatabaseWorker encerrado: %d janela(s) incompleta(s) gravada(s) e conexão fechada na thread %d.",
            len(ultima), threading.get_ident(),
        )
        # O quit() pode ser chamado de dentro da própria thread: o laço de eventos dela
        # termina assim que este slot voltar.
        self.thread().quit()

    def _gravar_janelas(self, janelas):
        if not janelas:
            return

        if self._conn is None:
            # Avisa uma vez só: chegam duas janelas por segundo e o log ficaria inundado.
            if not self._avisou_sem_conexao:
                logger.error("Leituras descartadas: a conexão do DatabaseWorker não está aberta.")
                self._avisou_sem_conexao = True
            return

        try:
            with self._conn:
                LeituraRepository.inserir_lote(janelas, conn=self._conn)
        except sqlite3.Error as erro:
            logger.error("Falha ao gravar %d janela(s) de leituras. Rollback executado: %s.", len(janelas), erro)
