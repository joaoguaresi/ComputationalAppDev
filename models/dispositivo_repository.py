import logging
from contextlib import closing
from datetime import datetime

from database.connection import Database
from models.dispositivo import Dispositivo

logger = logging.getLogger("smartgrid")


class DispositivoRepository:
    """CRUD da tabela dispositivos.

    Erros do SQLite não são tratados aqui e sobem para quem chamou: tag repetida
    (UNIQUE), status fora de ABERTO/FECHADO (CHECK) ou exclusão de um dispositivo
    com eventos vinculados (FOREIGN KEY) geram sqlite3.IntegrityError.
    """

    @staticmethod
    def inserir(dispositivo) -> int:
        """Grava um novo dispositivo e devolve o id gerado pelo banco."""
        with closing(Database.get_connection()) as conn:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO dispositivos (tag, tipo, status, ultima_atualizacao) VALUES (?, ?, ?, ?)",
                    (
                        dispositivo.tag,
                        dispositivo.tipo,
                        dispositivo.status,
                        dispositivo.ultima_atualizacao.strftime(Database.FORMATO_DATA_HORA),
                    ),
                )
                dispositivo.id = cursor.lastrowid

        logger.info("Dispositivo %s cadastrado com id %d.", dispositivo.tag, dispositivo.id)
        return dispositivo.id

    @classmethod
    def listar(cls) -> list:
        with closing(Database.get_connection()) as conn:
            linhas = conn.execute(
                "SELECT id, tag, tipo, status, ultima_atualizacao FROM dispositivos ORDER BY id"
            ).fetchall()

        return [cls._para_dispositivo(linha) for linha in linhas]

    @classmethod
    def buscar_por_tag(cls, tag):
        """Dispositivo com a tag informada, ou None se ela não existir."""
        with closing(Database.get_connection()) as conn:
            linha = conn.execute(
                "SELECT id, tag, tipo, status, ultima_atualizacao FROM dispositivos WHERE tag = ?",
                (tag,),
            ).fetchone()

        if linha is None:
            return None
        return cls._para_dispositivo(linha)

    @classmethod
    def atualizar_status(cls, tag, status, conn=None) -> bool:
        """Altera o status (ABERTO/FECHADO) e a data da última atualização.

        Sem conn, abre a própria conexão, faz commit e fecha. Com conn, executa dentro
        da transação de quem chamou, sem commit nem close: assim o corte de emergência
        grava o status e o evento juntos, ou nenhum dos dois. Nesse caso, quem chamou
        é que sabe se houve commit e registra o resultado no log.
        Devolve False se a tag não existir.
        """
        if conn is not None:
            return cls._gravar_status(conn, tag, status)

        with closing(Database.get_connection()) as nova_conn:
            with nova_conn:
                alterado = cls._gravar_status(nova_conn, tag, status)

        if alterado:
            logger.info("Status do dispositivo %s alterado para %s.", tag, status)
        return alterado

    @staticmethod
    def remover(tag) -> bool:
        """Exclui o dispositivo. Devolve False se a tag não existir."""
        with closing(Database.get_connection()) as conn:
            with conn:
                removido = conn.execute("DELETE FROM dispositivos WHERE tag = ?", (tag,)).rowcount > 0

        if not removido:
            logger.warning("Dispositivo %s não encontrado para exclusão.", tag)
            return False

        logger.info("Dispositivo %s excluído.", tag)
        return True

    @staticmethod
    def _gravar_status(conn, tag, status) -> bool:
        agora = datetime.now().strftime(Database.FORMATO_DATA_HORA)
        cursor = conn.execute(
            "UPDATE dispositivos SET status = ?, ultima_atualizacao = ? WHERE tag = ?",
            (status, agora, tag),
        )
        if cursor.rowcount == 0:
            logger.warning("Dispositivo %s não encontrado para alterar o status.", tag)
            return False
        return True

    @staticmethod
    def _para_dispositivo(linha) -> Dispositivo:
        """Converte uma linha da tabela dispositivos no model Dispositivo."""
        return Dispositivo(
            linha["tag"],
            linha["tipo"],
            linha["status"],
            datetime.strptime(linha["ultima_atualizacao"], Database.FORMATO_DATA_HORA),
            linha["id"],
        )
