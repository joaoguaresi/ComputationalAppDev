import logging
import sqlite3
import threading

from PySide6.QtCore import QObject, Signal, Slot

from database.connection import Database

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

    @Slot()
    def abrir(self):
        """Abre a conexão do worker. Ligado ao started da QThread, roda na thread do banco."""
        try:
            self._conn = Database.get_connection()
        except sqlite3.Error as erro:
            logger.error("DatabaseWorker: falha ao abrir a conexão com o banco: %s", erro)
            self.falhou.emit(str(erro))
            return

        logger.info("DatabaseWorker iniciado: conexão aberta na thread %d.", threading.get_ident())

    @Slot()
    def encerrar(self):
        """Fecha a conexão e termina o laço de eventos da thread do banco.

        O pedido chega pela fila depois dos que já estavam nela: o trabalho pendente
        termina antes, e nada é interrompido no meio de uma transação.
        """
        if self._conn is not None:
            self._conn.close()
            self._conn = None

        logger.info("DatabaseWorker encerrado: conexão fechada na thread %d.", threading.get_ident())
        # O quit() pode ser chamado de dentro da própria thread: o laço de eventos dela
        # termina assim que este slot voltar.
        self.thread().quit()
