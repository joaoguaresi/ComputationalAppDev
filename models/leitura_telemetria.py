"""Leitura de telemetria da placa, convertida de contagens do ADC para grandezas físicas."""

from datetime import datetime

from models.protocolo import ADC_MAXIMO

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

    def __init__(self, fator_tensao=FATOR_TENSAO_PADRAO,
                 sensibilidade_corrente=SENSIBILIDADE_PADRAO,
                 zero_corrente_adc=ZERO_CORRENTE_PADRAO):
        self.fator_tensao = fator_tensao
        self.sensibilidade_corrente = sensibilidade_corrente
        self.zero_corrente_adc = zero_corrente_adc

    def converter_tensao(self, a0) -> float:
        return a0 * self.fator_tensao

    def converter_corrente(self, a1) -> float:
        """I = (contagens acima do zero x volts por contagem) / sensibilidade. Pode ser negativa."""
        volts_por_contagem = TENSAO_REFERENCIA_ADC / ADC_MAXIMO
        return (a1 - self.zero_corrente_adc) * volts_por_contagem / self.sensibilidade_corrente


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
