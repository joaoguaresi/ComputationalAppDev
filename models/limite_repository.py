import logging
from contextlib import closing

from database.connection import Database
from models.limite import Limite

logger = logging.getLogger("smartgrid")


class LimiteRepository:
    """CRUD da tabela limites, que guarda os limites de segurança do QDialog de limites.

    O parametro (ex.: CORRENTE_MAX) é a chave natural da tabela (UNIQUE), por isso a
    busca, a atualização e a exclusão são feitas por ele. O dispositivo é informado pela
    tag, como no EventoRepository: na gravação, o SELECT interno troca a tag pelo id da
    tabela dispositivos (chave estrangeira); na leitura, o LEFT JOIN traz a tag de volta.

    Os métodos de escrita recebem conn opcional. Sem conn, abrem a própria conexão, fazem
    commit e fecham. Com conn, executam dentro da transação de quem chamou, sem commit nem
    close: assim o QDialog grava todos os limites juntos, ou nenhum.

    Erros do SQLite não são tratados aqui e sobem para quem chamou, como nos outros
    repositórios: parâmetro repetido no inserir (UNIQUE) ou valor zero, negativo ou não
    numérico (CHECK) geram sqlite3.IntegrityError.
    """

    @classmethod
    def inserir(cls, limite, conn=None) -> int:
        """Grava um limite novo e devolve o id gerado pelo banco."""
        cursor = cls._executar(
            """
            INSERT INTO limites (parametro, valor, unidade, dispositivo_id)
            VALUES (?, ?, ?, (SELECT id FROM dispositivos WHERE tag = ?))
            """,
            cls._parametros(limite),
            conn,
        )
        limite.id = cursor.lastrowid

        if conn is None:
            logger.info("Limite %s cadastrado: %s.", limite.parametro, limite.get_valor_formatado())
        return limite.id

    @classmethod
    def salvar(cls, limite, conn=None):
        """Insere o limite se o parâmetro ainda não existe, ou atualiza o que já existe.

        É o upsert do SQLite: o ON CONFLICT (parametro) aproveita a restrição UNIQUE e, em
        vez de falhar com IntegrityError, atualiza a linha do parâmetro num único comando.
        O id não é lido de volta, porque no caminho do UPDATE o lastrowid não traz o id da
        linha atualizada.
        """
        cls._executar(
            """
            INSERT INTO limites (parametro, valor, unidade, dispositivo_id)
            VALUES (?, ?, ?, (SELECT id FROM dispositivos WHERE tag = ?))
            ON CONFLICT (parametro) DO UPDATE SET
                valor = excluded.valor,
                unidade = excluded.unidade,
                dispositivo_id = excluded.dispositivo_id
            """,
            cls._parametros(limite),
            conn,
        )

        if conn is None:
            logger.info("Limite %s salvo: %s.", limite.parametro, limite.get_valor_formatado())

    @classmethod
    def listar_todos(cls) -> list:
        """Todos os limites gravados, em ordem de parâmetro."""
        with closing(Database.get_connection()) as conn:
            linhas = conn.execute(
                """
                SELECT l.id, l.parametro, l.valor, l.unidade, d.tag AS dispositivo_tag
                FROM limites AS l
                LEFT JOIN dispositivos AS d ON d.id = l.dispositivo_id
                ORDER BY l.parametro
                """
            ).fetchall()

        return [cls._para_limite(linha) for linha in linhas]

    @classmethod
    def buscar_por_parametro(cls, parametro):
        """Limite do parâmetro informado, ou None se ele ainda não foi gravado."""
        with closing(Database.get_connection()) as conn:
            linha = conn.execute(
                """
                SELECT l.id, l.parametro, l.valor, l.unidade, d.tag AS dispositivo_tag
                FROM limites AS l
                LEFT JOIN dispositivos AS d ON d.id = l.dispositivo_id
                WHERE l.parametro = ?
                """,
                (parametro,),
            ).fetchone()

        if linha is None:
            return None
        return cls._para_limite(linha)

    @classmethod
    def atualizar(cls, limite, conn=None) -> bool:
        """Regrava o valor, a unidade e o dispositivo do parâmetro. Devolve False se o
        parâmetro ainda não foi gravado."""
        cursor = cls._executar(
            """
            UPDATE limites
            SET valor = ?, unidade = ?, dispositivo_id = (SELECT id FROM dispositivos WHERE tag = ?)
            WHERE parametro = ?
            """,
            (limite.valor, limite.unidade, limite.dispositivo_tag, limite.parametro),
            conn,
        )

        if cursor.rowcount == 0:
            logger.warning("Limite %s não encontrado para atualização.", limite.parametro)
            return False

        if conn is None:
            logger.info("Limite %s atualizado para %s.", limite.parametro, limite.get_valor_formatado())
        return True

    @classmethod
    def excluir(cls, parametro, conn=None) -> bool:
        """Remove o limite do parâmetro. Devolve False se ele não existir."""
        cursor = cls._executar("DELETE FROM limites WHERE parametro = ?", (parametro,), conn)

        if cursor.rowcount == 0:
            logger.warning("Limite %s não encontrado para exclusão.", parametro)
            return False

        if conn is None:
            logger.info("Limite %s excluído.", parametro)
        return True

    @staticmethod
    def _executar(sql, parametros, conn):
        """Executa um comando de escrita e devolve o cursor.

        Com conn, usa a transação de quem chamou, sem commit nem close. Sem conn, abre a
        própria conexão: o with faz o commit (ou o rollback, se der erro) e o closing a
        fecha, o que o with sozinho não faz. O rowcount e o lastrowid do cursor continuam
        legíveis depois que a conexão fecha.
        """
        if conn is not None:
            return conn.execute(sql, parametros)

        with closing(Database.get_connection()) as nova_conn:
            with nova_conn:
                return nova_conn.execute(sql, parametros)

    @staticmethod
    def _parametros(limite) -> tuple:
        """Valores do limite na ordem dos placeholders do INSERT."""
        return (limite.parametro, limite.valor, limite.unidade, limite.dispositivo_tag)

    @staticmethod
    def _para_limite(linha) -> Limite:
        """Converte uma linha do SELECT no model Limite."""
        return Limite(
            linha["parametro"],
            linha["valor"],
            linha["unidade"],
            linha["dispositivo_tag"],
            linha["id"],
        )
