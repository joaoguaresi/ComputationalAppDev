import logging

from models.config_manager import ConfigManager
from models.leitura_media import LeituraMedia

logger = logging.getLogger("smartgrid")


class AgregadorLeituras:
    """Junta as leituras da placa (200 por segundo) em janelas de taxa_amostragem_ms e
    devolve a média de cada janela, que é o que fica gravado na tabela leituras.

    As janelas são alinhadas no relógio, em múltiplos de taxa_amostragem_ms: com 500 ms,
    uma janela vai de 14:00:12.000 a 14:00:12.499 e a seguinte começa em 14:00:12.500.
    O horário gravado é o início da janela.

    A potência da janela é a média das potências de cada amostra, e não a tensão média
    vezes a corrente média: com tensão e corrente variando juntas, as duas contas dão
    resultados diferentes, e só a primeira é a potência média de verdade.

    Uma janela fecha quando chega a primeira leitura de outra janela. A janela em
    andamento no encerramento é fechada por finalizar().
    """

    CHAVE_CONFIG = "taxa_amostragem_ms"

    # 500 ms a 200 Hz: 100 amostras por linha e 2 linhas por segundo no banco.
    TAXA_PADRAO_MS = 500
    TAXA_MINIMA_MS = 100
    TAXA_MAXIMA_MS = 60000

    def __init__(self, taxa_amostragem_ms=TAXA_PADRAO_MS):
        if not self.taxa_valida(taxa_amostragem_ms):
            raise ValueError(
                f"taxa_amostragem_ms precisa ser um inteiro entre {self.TAXA_MINIMA_MS} e {self.TAXA_MAXIMA_MS}."
            )
        self.taxa_ms = taxa_amostragem_ms
        self._inicio_janela = None
        self._limpar_somas()

    @classmethod
    def do_config(cls):
        """Agregador com a taxa_amostragem_ms do config.json (ou a padrão, se faltar ou for inválida)."""
        taxa = ConfigManager.get(cls.CHAVE_CONFIG, cls.TAXA_PADRAO_MS)
        if not cls.taxa_valida(taxa):
            logger.warning(
                "Valor inválido para '%s' no config.json: %r. Usando o padrão de %d ms.",
                cls.CHAVE_CONFIG, taxa, cls.TAXA_PADRAO_MS,
            )
            taxa = cls.TAXA_PADRAO_MS
        return cls(taxa)

    @classmethod
    def taxa_valida(cls, taxa) -> bool:
        # No Python, bool é subclasse de int: true/false no JSON não vale como taxa.
        if isinstance(taxa, bool) or not isinstance(taxa, int):
            return False
        return cls.TAXA_MINIMA_MS <= taxa <= cls.TAXA_MAXIMA_MS

    def adicionar(self, leitura) -> list:
        """Inclui uma LeituraTelemetria e devolve as janelas que ela fechou (nenhuma ou uma)."""
        timestamp_ms = LeituraMedia.para_ms(leitura.timestamp)
        inicio = timestamp_ms - timestamp_ms % self.taxa_ms

        fechadas = []
        # Qualquer mudança de janela fecha a atual, inclusive se o relógio voltar (ajuste
        # de horário): a ordem cronológica é garantida pelo ORDER BY das consultas.
        if self._inicio_janela is not None and inicio != self._inicio_janela:
            fechadas.append(self._fechar_janela())

        if self._inicio_janela is None:
            self._inicio_janela = inicio

        self._soma_tensao += leitura.tensao_v
        self._soma_corrente += leitura.corrente_a
        self._soma_potencia += leitura.calcular_potencia()
        self._amostras += 1
        return fechadas

    def finalizar(self) -> list:
        """Fecha a janela em andamento e devolve a média dela (lista vazia se não houver)."""
        if self._amostras == 0:
            return []
        return [self._fechar_janela()]

    def _fechar_janela(self) -> LeituraMedia:
        media = LeituraMedia(
            self._inicio_janela,
            self._soma_tensao / self._amostras,
            self._soma_corrente / self._amostras,
            self._soma_potencia / self._amostras,
            self._amostras,
        )
        self._inicio_janela = None
        self._limpar_somas()
        return media

    def _limpar_somas(self):
        self._soma_tensao = 0.0
        self._soma_corrente = 0.0
        self._soma_potencia = 0.0
        self._amostras = 0
