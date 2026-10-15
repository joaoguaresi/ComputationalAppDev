import logging
from contextlib import closing
from datetime import datetime

from database.connection import Database
from models.evento_historico import EventoHistorico

logger = logging.getLogger("smartgrid")


class EventoRepository:
    """CRUD da tabela eventos, que guarda o histórico exibido na QTableWidget.

    Todo SELECT lista as colunas e cada valor é lido pelo nome (sqlite3.Row), nunca
    pela posição, que pode mudar quando o esquema é migrado com ALTER TABLE.

    O dispositivo do evento é informado pela tag (ex.: DJ-PRINCIPAL). Na gravação, o
    SELECT interno troca a tag pelo id da tabela dispositivos (chave estrangeira); na
    leitura, o LEFT JOIN traz a tag de volta. Evento sem dispositivo fica com NULL.

    Erros do SQLite não são tratados aqui e sobem para quem chamou, como no
    DispositivoRepository.
    """

    @classmethod
    def inserir(cls, evento, conn=None) -> int:
        """Grava o evento e devolve o id gerado pelo banco.

        Sem conn, abre a própria conexão, faz commit e fecha. Com conn, executa dentro
        da transação de quem chamou, sem commit nem close: assim o corte de emergência
        grava o status do disjuntor e o evento juntos, ou nenhum dos dois.
        """
        if conn is not None:
            return cls._gravar(conn, evento)

        with closing(Database.get_connection()) as nova_conn:
            with nova_conn:
                evento_id = cls._gravar(nova_conn, evento)
        return evento_id

    @classmethod
    def listar_todos(cls) -> list:
        """Todos os eventos gravados, do mais recente para o mais antigo."""
        with closing(Database.get_connection()) as conn:
            linhas = conn.execute(
                """
                SELECT e.id, e.data_hora, e.tipo_evento, e.descricao, e.valor_medido, e.unidade,
                       d.tag AS dispositivo_tag
                FROM eventos AS e
                LEFT JOIN dispositivos AS d ON d.id = e.dispositivo_id
                ORDER BY e.data_hora DESC, e.id DESC
                """
            ).fetchall()

        return [cls._para_evento(linha) for linha in linhas]

    @classmethod
    def buscar_por_id(cls, evento_id):
        """Evento com o id informado, ou None se ele não existir."""
        with closing(Database.get_connection()) as conn:
            linha = conn.execute(
                """
                SELECT e.id, e.data_hora, e.tipo_evento, e.descricao, e.valor_medido, e.unidade,
                       d.tag AS dispositivo_tag
                FROM eventos AS e
                LEFT JOIN dispositivos AS d ON d.id = e.dispositivo_id
                WHERE e.id = ?
                """,
                (evento_id,),
            ).fetchone()

        if linha is None:
            return None
        return cls._para_evento(linha)

    @classmethod
    def atualizar(cls, evento) -> bool:
        """Regrava os dados do evento com o mesmo id. Devolve False se o id não existir."""
        with closing(Database.get_connection()) as conn:
            with conn:
                alterado = conn.execute(
                    """
                    UPDATE eventos
                    SET data_hora = ?, tipo_evento = ?, descricao = ?, valor_medido = ?, unidade = ?,
                        dispositivo_id = (SELECT id FROM dispositivos WHERE tag = ?)
                    WHERE id = ?
                    """,
                    (*cls._parametros(evento), evento.id),
                ).rowcount > 0

        if not alterado:
            logger.warning("Evento %s não encontrado para atualização.", evento.id)
            return False

        logger.info("Evento %s do histórico atualizado.", evento.id)
        return True

    @staticmethod
    def excluir(evento_id) -> bool:
        """Remove o evento do histórico. Devolve False se o id não existir."""
        with closing(Database.get_connection()) as conn:
            with conn:
                removido = conn.execute("DELETE FROM eventos WHERE id = ?", (evento_id,)).rowcount > 0

        if not removido:
            logger.warning("Evento %s não encontrado para exclusão.", evento_id)
            return False

        logger.info("Evento %s excluído do histórico.", evento_id)
        return True

    @classmethod
    def _gravar(cls, conn, evento) -> int:
        cursor = conn.execute(
            """
            INSERT INTO eventos (data_hora, tipo_evento, descricao, valor_medido, unidade, dispositivo_id)
            VALUES (?, ?, ?, ?, ?, (SELECT id FROM dispositivos WHERE tag = ?))
            """,
            cls._parametros(evento),
        )
        evento.id = cursor.lastrowid
        return evento.id

    @staticmethod
    def _parametros(evento) -> tuple:
        """Valores do evento na ordem dos placeholders do INSERT e do UPDATE."""
        return (
            evento.timestamp.strftime(Database.FORMATO_DATA_HORA),
            evento.tipo,
            evento.descricao,
            evento.valor,
            evento.unidade,
            evento.dispositivo_tag,
        )

    @staticmethod
    def _para_evento(linha) -> EventoHistorico:
        """Converte uma linha do SELECT no model EventoHistorico."""
        return EventoHistorico(
            linha["tipo_evento"],
            linha["descricao"],
            linha["valor_medido"],
            linha["unidade"],
            datetime.strptime(linha["data_hora"], Database.FORMATO_DATA_HORA),
            linha["dispositivo_tag"],
            linha["id"],
        )
