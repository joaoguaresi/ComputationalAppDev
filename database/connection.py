import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime

from database import schema

logger = logging.getLogger("smartgrid")

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Database:
    """Banco SQLite da aplicação, criado automaticamente em data/smartgrid.db.

    Cada operação abre a própria conexão com get_connection() e a fecha ao terminar.
    """

    PASTA_DATA = os.path.join(PASTA_PROJETO, "data")
    CAMINHO = os.path.join(PASTA_DATA, "smartgrid.db")

    # Tempo que uma conexão espera quando outra está com o banco bloqueado,
    # antes de falhar com "database is locked".
    TIMEOUT_SEGUNDOS = 5.0

    # Datas ficam como texto ISO: ordenam certo no ORDER BY e funcionam com as
    # funções de data do SQLite.
    FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def get_connection(cls):
        """Abre uma conexão nova com timeout e chaves estrangeiras ativas.

        O PRAGMA foreign_keys vale só para a conexão em que foi executado, por isso
        roda em toda abertura e não apenas no init_db(). Quem abre a conexão também
        a fecha: o with conn: faz commit/rollback, mas não chama close().
        """
        conn = sqlite3.connect(cls.CAMINHO, timeout=cls.TIMEOUT_SEGUNDOS)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @classmethod
    def init_db(cls) -> bool:
        """Cria o banco e as tabelas se ainda não existirem, cadastra os dispositivos
        padrão e valida o esquema. Devolve False se o banco não puder ser usado."""
        try:
            os.makedirs(cls.PASTA_DATA, exist_ok=True)
            with closing(cls.get_connection()) as conn:
                with conn:
                    for comando in schema.CRIAR_TABELAS:
                        conn.execute(comando)

                    agora = datetime.now().strftime(cls.FORMATO_DATA_HORA)
                    conn.executemany(
                        schema.INSERIR_DISPOSITIVO_PADRAO,
                        [(tag, tipo, status, agora) for tag, tipo, status in schema.DISPOSITIVOS_PADRAO],
                    )

                cls._validar_esquema(conn)
        except (sqlite3.Error, OSError) as erro:
            logger.critical("Não foi possível inicializar o banco %s: %s", cls.CAMINHO, erro)
            return False

        logger.info("Conexão com SQLite estabelecida e esquema validado.")
        return True

    @staticmethod
    def _validar_esquema(conn):
        """Confere as colunas de cada tabela e se as chaves estrangeiras estão ativas.

        CREATE TABLE IF NOT EXISTS não altera uma tabela que já existia, então um
        banco antigo com outro formato só é detectado aqui.
        """
        for tabela, colunas in schema.COLUNAS_ESPERADAS.items():
            linhas = conn.execute("SELECT name FROM pragma_table_info(?)", (tabela,))
            encontradas = {linha["name"] for linha in linhas}
            faltando = [coluna for coluna in colunas if coluna not in encontradas]
            if faltando:
                raise sqlite3.DatabaseError(f"tabela {tabela} sem a(s) coluna(s): {', '.join(faltando)}")

        linha = conn.execute("PRAGMA foreign_keys").fetchone()
        if linha is None or linha[0] != 1:
            raise sqlite3.DatabaseError("PRAGMA foreign_keys não está ativo")
