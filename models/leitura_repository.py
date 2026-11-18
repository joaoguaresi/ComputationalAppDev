from contextlib import closing

from database.connection import Database
from models.filtro_historico import FiltroHistorico
from models.leitura_media import LeituraMedia


class LeituraRepository:
    """Gravação e consulta da tabela leituras (a média de cada janela de taxa_amostragem_ms).

    Telemetria não é alterada depois de gravada, por isso não há atualizar nem excluir:
    o repositório grava lotes e consulta o histórico.

    Todos os métodos aceitam conn opcional. O DatabaseWorker mantém uma conexão própria
    na thread dele (o sqlite3 não deixa usar uma conexão em outra thread) e a passa aqui.
    Com conn, o repositório não faz commit nem close: quem controla a transação é quem
    chamou. Sem conn, abre a própria conexão, faz commit e fecha.

    Erros do SQLite não são tratados aqui e sobem para quem chamou, como nos outros
    repositórios: um valor fora dos CHECK da tabela gera sqlite3.IntegrityError.
    """

    @staticmethod
    def inserir_lote(leituras, conn=None) -> int:
        """Grava as leituras com um único executemany e devolve quantas foram gravadas."""
        parametros = [
            (leitura.timestamp_ms, leitura.tensao_v, leitura.corrente_a, leitura.potencia_w, leitura.amostras)
            for leitura in leituras
        ]
        if not parametros:
            return 0

        sql = """
            INSERT INTO leituras (timestamp_ms, tensao_v, corrente_a, potencia_w, amostras)
            VALUES (?, ?, ?, ?, ?)
        """
        if conn is not None:
            conn.executemany(sql, parametros)
            return len(parametros)

        with closing(Database.get_connection()) as nova_conn:
            with nova_conn:
                nova_conn.executemany(sql, parametros)
        return len(parametros)

    @classmethod
    def contar(cls, filtro, conn=None) -> int:
        """Quantas leituras o filtro devolveria, sem buscá-las.

        Valida o filtro antes do SQL: um filtro inválido levanta ValueError.
        """
        filtro.validar()

        if filtro.modo == FiltroHistorico.ULTIMAS:
            sql = "SELECT COUNT(*) FROM leituras"
            parametros = ()
        else:
            sql = "SELECT COUNT(*) FROM leituras WHERE timestamp_ms BETWEEN ? AND ?"
            parametros = (filtro.inicio_ms(), filtro.fim_ms())

        total = cls._consultar(sql, parametros, conn)[0][0]
        if filtro.modo == FiltroHistorico.ULTIMAS:
            return min(total, filtro.quantidade)
        return total

    @classmethod
    def listar(cls, filtro, conn=None, agrupar=1) -> list:
        """Leituras do filtro, da mais antiga para a mais recente (a ordem do gráfico).

        Com agrupar > 1 (só no intervalo), cada grupo de leituras seguidas vira um ponto:
        a média de tensão, corrente e potência ponderada pelo número de amostras de cada
        janela, com o horário da primeira. Assim um intervalo longo chega ao gráfico com
        menos pontos, sem trazer todas as linhas para a memória.

        Valida o filtro antes do SQL: um filtro inválido levanta ValueError.
        """
        filtro.validar()
        if isinstance(agrupar, bool) or not isinstance(agrupar, int) or agrupar < 1:
            raise ValueError("agrupar precisa ser um número inteiro maior ou igual a 1.")
        if agrupar > 1 and filtro.modo != FiltroHistorico.INTERVALO:
            raise ValueError("O agrupamento só vale para a consulta por intervalo.")

        if agrupar > 1:
            # ROW_NUMBER numera as leituras do intervalo em ordem; ordem / agrupar (divisão
            # inteira) dá o mesmo número para cada bloco de "agrupar" leituras seguidas.
            sql = """
                SELECT NULL AS id,
                       MIN(timestamp_ms) AS timestamp_ms,
                       SUM(tensao_v * amostras) / SUM(amostras) AS tensao_v,
                       SUM(corrente_a * amostras) / SUM(amostras) AS corrente_a,
                       SUM(potencia_w * amostras) / SUM(amostras) AS potencia_w,
                       SUM(amostras) AS amostras
                FROM (
                    SELECT timestamp_ms, tensao_v, corrente_a, potencia_w, amostras,
                           ROW_NUMBER() OVER (ORDER BY timestamp_ms, id) - 1 AS ordem
                    FROM leituras
                    WHERE timestamp_ms BETWEEN ? AND ?
                )
                GROUP BY ordem / ?
                ORDER BY timestamp_ms
            """
            linhas = cls._consultar(sql, (filtro.inicio_ms(), filtro.fim_ms(), agrupar), conn)
            return [cls._para_leitura(linha) for linha in linhas]

        if filtro.modo == FiltroHistorico.ULTIMAS:
            # A consulta interna pega as N mais recentes pelo índice do horário; a externa
            # devolve essas N em ordem cronológica.
            sql = """
                SELECT id, timestamp_ms, tensao_v, corrente_a, potencia_w, amostras
                FROM (
                    SELECT id, timestamp_ms, tensao_v, corrente_a, potencia_w, amostras
                    FROM leituras
                    ORDER BY timestamp_ms DESC, id DESC
                    LIMIT ?
                )
                ORDER BY timestamp_ms, id
            """
            parametros = (filtro.quantidade,)
        else:
            sql = """
                SELECT id, timestamp_ms, tensao_v, corrente_a, potencia_w, amostras
                FROM leituras
                WHERE timestamp_ms BETWEEN ? AND ?
                ORDER BY timestamp_ms, id
            """
            parametros = (filtro.inicio_ms(), filtro.fim_ms())

        linhas = cls._consultar(sql, parametros, conn)
        return [cls._para_leitura(linha) for linha in linhas]

    @staticmethod
    def _consultar(sql, parametros, conn) -> list:
        """Executa um SELECT na conexão recebida ou numa própria, que é fechada no fim."""
        if conn is not None:
            return conn.execute(sql, parametros).fetchall()

        with closing(Database.get_connection()) as nova_conn:
            return nova_conn.execute(sql, parametros).fetchall()

    @staticmethod
    def _para_leitura(linha) -> LeituraMedia:
        """Converte uma linha do SELECT no model LeituraMedia."""
        return LeituraMedia(
            linha["timestamp_ms"],
            linha["tensao_v"],
            linha["corrente_a"],
            linha["potencia_w"],
            linha["amostras"],
            linha["id"],
        )
