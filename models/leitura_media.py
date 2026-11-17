from datetime import datetime


class LeituraMedia:
    """Média das leituras da placa numa janela de taxa_amostragem_ms, como fica gravada
    na tabela leituras.

    É diferente da LeituraTelemetria, que é uma única amostra do $DAT: aqui a potência é
    a média das potências de cada amostra (não a tensão média vezes a corrente média) e
    amostras diz quantas leituras da placa entraram na média. Corrente e potência podem
    ser negativas, porque o sensor de corrente é bidirecional.
    """

    def __init__(self, timestamp_ms, tensao_v, corrente_a, potencia_w, amostras, leitura_id=None):
        self.id = leitura_id
        self.timestamp_ms = timestamp_ms
        self.tensao_v = tensao_v
        self.corrente_a = corrente_a
        self.potencia_w = potencia_w
        self.amostras = amostras

    @staticmethod
    def para_ms(momento) -> int:
        """Data/hora local em milissegundos desde 1970, o formato da coluna timestamp_ms.

        round() em vez de int(): o produto de ponto flutuante pode dar 344,9999 em vez de
        345, e o int() cortaria 1 ms.
        """
        return round(momento.timestamp() * 1000)

    @staticmethod
    def para_datetime(timestamp_ms) -> datetime:
        """Volta os milissegundos da coluna timestamp_ms para data/hora local."""
        return datetime.fromtimestamp(timestamp_ms / 1000)

    def get_datetime(self) -> datetime:
        return LeituraMedia.para_datetime(self.timestamp_ms)

    def get_data_hora(self) -> str:
        """Data e hora com milissegundos, ex.: 2026-11-20 14:03:12.345."""
        return self.get_datetime().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
