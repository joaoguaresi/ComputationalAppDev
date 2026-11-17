import logging
import sqlite3
import threading

from PySide6.QtCore import QObject, Signal, Slot

from database.connection import Database
from models.agregador_leituras import AgregadorLeituras
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
