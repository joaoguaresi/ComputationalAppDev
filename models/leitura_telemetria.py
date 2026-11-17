"""Leitura de telemetria da placa, convertida de contagens do ADC para grandezas físicas."""

import logging
from collections import deque
from datetime import datetime

from models.config_manager import ConfigManager
from models.protocolo import ADC_MAXIMO

logger = logging.getLogger("smartgrid")

# O ADC do Arduino Uno mede de 0 a 5 V em 0 a 1023 contagens.
TENSAO_REFERENCIA_ADC = 5.0


class Calibracao:
    """Fatores que transformam as contagens do ADC (0 a 1023) em volts e ampères.

    Tensão (A0): o condicionamento leva 0 a 12 V do barramento para a faixa do ADC,
    então 12 V = 1023. Corrente (A1): ACS712-30A, com 66 mV/A e 0 A no meio da escala
    (cerca de 512); acima do zero a corrente é positiva, abaixo é negativa.
    """

    FATOR_TENSAO_PADRAO = 12.0 / ADC_MAXIMO
    SENSIBILIDADE_PADRAO = 0.066
    ZERO_CORRENTE_PADRAO = 512.0

    # Um zero calibrado mais longe que isso do meio da escala (cerca de 3,7 A)
    # indica que havia carga ligada durante a calibração.
    DESVIO_MAXIMO_ZERO = 50

    def __init__(self, fator_tensao=FATOR_TENSAO_PADRAO,
                 sensibilidade_corrente=SENSIBILIDADE_PADRAO,
                 zero_corrente_adc=ZERO_CORRENTE_PADRAO):
        self.fator_tensao = fator_tensao
        self.sensibilidade_corrente = sensibilidade_corrente
        self.zero_corrente_adc = zero_corrente_adc

    @classmethod
    def do_config(cls):
        """Calibração com os fatores do config.json (ou os padrões, se a chave não existir)."""
        return cls(
            ConfigManager.get("fator_tensao", cls.FATOR_TENSAO_PADRAO),
            ConfigManager.get("sensibilidade_corrente", cls.SENSIBILIDADE_PADRAO),
            ConfigManager.get("zero_corrente_adc", cls.ZERO_CORRENTE_PADRAO),
        )

    def calibrar_zero(self, amostras_a1) -> float:
        """Define o zero da corrente pela média de A1 medida sem carga (relé desligado).

        Usado na bancada oficial, logo depois de conectar, porque o firmware começa
        com o relé desligado. Na montagem com potenciômetro o zero fica fixo.
        """
        amostras = list(amostras_a1)
        if not amostras:
            raise ValueError("nenhuma amostra de A1 para calibrar o zero da corrente")

        media = sum(amostras) / len(amostras)
        if abs(media - self.ZERO_CORRENTE_PADRAO) > self.DESVIO_MAXIMO_ZERO:
            logger.warning(
                "Zero da corrente calibrado em %.1f, longe de 512: confira se havia carga ligada.", media
            )
        else:
            logger.info("Zero da corrente calibrado em %.1f (média de %d amostras).", media, len(amostras))

        self.zero_corrente_adc = media
        return media

    def converter_tensao(self, a0) -> float:
        return a0 * self.fator_tensao

    def converter_corrente(self, a1) -> float:
        """I = (contagens acima do zero x volts por contagem) / sensibilidade. Pode ser negativa."""
        volts_por_contagem = TENSAO_REFERENCIA_ADC / ADC_MAXIMO
        return (a1 - self.zero_corrente_adc) * volts_por_contagem / self.sensibilidade_corrente


class MediaMovel:
    """Média das últimas N amostras, para suavizar a corrente (cerca de 74 mA por contagem)."""

    def __init__(self, janela=10):
        if janela < 1:
            raise ValueError("a janela da média móvel precisa ter pelo menos 1 amostra")
        self._valores = deque(maxlen=janela)

    def adicionar(self, valor) -> float:
        """Inclui a amostra nova e devolve a média atual."""
        self._valores.append(valor)
        return sum(self._valores) / len(self._valores)

    def limpar(self):
        self._valores.clear()


class LeituraTelemetria:
    """Uma amostra da placa: tensão, corrente, estado do relé e do botão.

    O sensor de corrente é bidirecional, então corrente e potência negativas são
    leituras válidas. O horário guarda milissegundos, porque a 200 Hz chegam até
    200 leituras no mesmo segundo.
    """

    def __init__(self, tensao_v, corrente_a, status_rele, status_botao,
                 timestamp=None, a0=None, a1=None):
        self.tensao_v = tensao_v
        self.corrente_a = corrente_a
        self.status_rele = status_rele
        self.status_botao = status_botao

        # Contagens cruas do ADC, guardadas para calibração e diagnóstico.
        self.a0 = a0
        self.a1 = a1

        if timestamp is None:
            timestamp = datetime.now()
        self.timestamp = timestamp

    @classmethod
    def de_pacote(cls, campos: dict, calibracao=None, timestamp=None):
        """Cria a leitura a partir dos campos de um $DAT (o valor de interpretar_linha)."""
        if calibracao is None:
            calibracao = Calibracao()
        return cls(
            calibracao.converter_tensao(campos["a0"]),
            calibracao.converter_corrente(campos["a1"]),
            campos["status_rele"],
            campos["status_botao"],
            timestamp,
            campos["a0"],
            campos["a1"],
        )

    def calcular_potencia(self) -> float:
        return self.tensao_v * self.corrente_a

    def rele_ligado(self) -> bool:
        return self.status_rele == 1

    def botao_pressionado(self) -> bool:
        return self.status_botao == 1

    def get_data_hora(self) -> str:
        """Data e hora com milissegundos, ex.: 2026-11-20 14:03:12.345."""
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def get_dados(self) -> dict:
        # O "+ 0.0" troca o -0.0 do arredondamento por 0.0 na tela.
        dicionario = {
            "tensao": round(self.tensao_v, 2) + 0.0,
            "corrente": round(self.corrente_a, 2) + 0.0,
            "potencia": round(self.calcular_potencia(), 2) + 0.0,
            "status_rele": self.status_rele,
            "status_botao": self.status_botao,
            "data_hora": self.get_data_hora(),
        }
        return dicionario
