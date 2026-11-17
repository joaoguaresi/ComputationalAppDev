from datetime import datetime

from models.leitura_media import LeituraMedia


class FiltroHistorico:
    """Filtro da consulta ao histórico de leituras: as últimas N ou um intervalo de data/hora.

    validar() levanta ValueError com a mensagem para o operador. A tela usa a mensagem
    num QMessageBox antes de pedir a consulta, e o LeituraRepository valida de novo antes
    do SQL, então um filtro inválido nunca chega ao banco.
    """

    ULTIMAS = "ULTIMAS"
    INTERVALO = "INTERVALO"

    # Teto das "últimas N": cada leitura vira um ponto do gráfico, e uma quantidade sem
    # limite poderia carregar a tabela inteira na memória.
    QUANTIDADE_MAXIMA = 10000

    FORMATO_DATA_HORA = "%d/%m/%Y %H:%M:%S"

    def __init__(self, modo, quantidade=None, inicio=None, fim=None):
        self.modo = modo
        self.quantidade = quantidade
        self.inicio = inicio
        self.fim = fim

    @classmethod
    def ultimas(cls, quantidade):
        return cls(cls.ULTIMAS, quantidade=quantidade)

    @classmethod
    def intervalo(cls, inicio, fim):
        return cls(cls.INTERVALO, inicio=inicio, fim=fim)

    def validar(self):
        """Levanta ValueError, com a mensagem para o operador, se o filtro não puder ser consultado."""
        if self.modo == FiltroHistorico.ULTIMAS:
            # No Python, bool é subclasse de int: True não vale como quantidade.
            if isinstance(self.quantidade, bool) or not isinstance(self.quantidade, int):
                raise ValueError("A quantidade de leituras precisa ser um número inteiro.")
            if not 1 <= self.quantidade <= FiltroHistorico.QUANTIDADE_MAXIMA:
                raise ValueError(
                    f"A quantidade de leituras precisa estar entre 1 e {FiltroHistorico.QUANTIDADE_MAXIMA}."
                )
            return

        if self.modo == FiltroHistorico.INTERVALO:
            if not isinstance(self.inicio, datetime) or not isinstance(self.fim, datetime):
                raise ValueError("Informe a data/hora de início e de fim do intervalo.")
            if self.inicio >= self.fim:
                raise ValueError("A data/hora de início precisa ser anterior à de fim.")
            return

        raise ValueError(f"Modo de filtro desconhecido: {self.modo}.")

    def inicio_ms(self) -> int:
        return LeituraMedia.para_ms(self.inicio)

    def fim_ms(self) -> int:
        return LeituraMedia.para_ms(self.fim)

    def descrever(self) -> str:
        """Texto do filtro para o log e para o aviso de consulta, ex.: "últimas 500 leituras"."""
        if self.modo == FiltroHistorico.ULTIMAS:
            return f"últimas {self.quantidade} leituras"
        formato = FiltroHistorico.FORMATO_DATA_HORA
        return f"leituras de {self.inicio.strftime(formato)} a {self.fim.strftime(formato)}"
