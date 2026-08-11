import math
import random
from datetime import datetime, timedelta

from models.medicao import Medicao


class SimuladorTelemetria:
    QUANTIDADE_PADRAO = 60
    INTERVALO_PADRAO = 60
    PERIODO_CICLO = 20

    TENSAO_NOMINAL = 220.0
    VARIACAO_TENSAO = 3.0

    CORRENTE_BASE = 5.5
    AMPLITUDE_CORRENTE = 2.0
    RUIDO_CORRENTE = 0.35
    CORRENTE_MINIMA = 0.5

    CORRENTE_PICO = 11.5
    DURACAO_PICO = 3
    PICO_ANTES_DO_FIM = 15

    SETPOINT_SUGERIDO = 2000.0

    def __init__(self, seed=None):
        self.aleatorio = random.Random(seed)
        self.passo = 0

    def gerar_historico(self, quantidade=None, intervalo_segundos=None, com_pico=True) -> list:
        if quantidade is None:
            quantidade = SimuladorTelemetria.QUANTIDADE_PADRAO
        if intervalo_segundos is None:
            intervalo_segundos = SimuladorTelemetria.INTERVALO_PADRAO

        agora = datetime.now()
        medicoes = []

        for indice in range(quantidade):
            recuo = (quantidade - 1 - indice) * intervalo_segundos
            timestamp = agora - timedelta(seconds=recuo)

            if com_pico and self._esta_no_pico(indice, quantidade):
                corrente = self._gerar_corrente_de_pico()
            else:
                corrente = self._gerar_corrente(indice)

            medicao = Medicao(self._gerar_tensao(), corrente, timestamp)
            medicoes.append(medicao)

        self.passo = quantidade
        return medicoes

    def proxima_medicao(self) -> Medicao:
        corrente = self._gerar_corrente(self.passo)
        self.passo = self.passo + 1
        return Medicao(self._gerar_tensao(), corrente, datetime.now())

    @staticmethod
    def extrair_series(medicoes) -> dict:
        dicionario = {
            "timestamps": [medicao.timestamp for medicao in medicoes],
            "segundos": [medicao.timestamp.timestamp() for medicao in medicoes],
            "tensao": [medicao.tensao_v for medicao in medicoes],
            "corrente": [medicao.corrente_a for medicao in medicoes],
            "potencia": [medicao.calcular_potencia() for medicao in medicoes],
        }
        return dicionario

    def _gerar_tensao(self) -> float:
        variacao = SimuladorTelemetria.VARIACAO_TENSAO
        ruido = self.aleatorio.uniform(-variacao, variacao)
        return SimuladorTelemetria.TENSAO_NOMINAL + ruido

    def _gerar_corrente(self, passo) -> float:
        angulo = 2 * math.pi * passo / SimuladorTelemetria.PERIODO_CICLO
        onda = SimuladorTelemetria.AMPLITUDE_CORRENTE * math.sin(angulo)

        ruido_max = SimuladorTelemetria.RUIDO_CORRENTE
        ruido = self.aleatorio.uniform(-ruido_max, ruido_max)

        corrente = SimuladorTelemetria.CORRENTE_BASE + onda + ruido

        if corrente < SimuladorTelemetria.CORRENTE_MINIMA:
            return SimuladorTelemetria.CORRENTE_MINIMA
        return corrente

    def _gerar_corrente_de_pico(self) -> float:
        ruido_max = SimuladorTelemetria.RUIDO_CORRENTE
        ruido = self.aleatorio.uniform(-ruido_max, ruido_max)
        return SimuladorTelemetria.CORRENTE_PICO + ruido

    def _esta_no_pico(self, indice, quantidade) -> bool:
        inicio = quantidade - SimuladorTelemetria.PICO_ANTES_DO_FIM
        if indice < inicio:
            return False
        return indice < inicio + SimuladorTelemetria.DURACAO_PICO
