from datetime import datetime


class Medicao:
    def __init__(self, tensao_v, corrente_a, timestamp=None):
        self.tensao_v = tensao_v
        self.corrente_a = corrente_a

        if timestamp is None:
            timestamp = datetime.now()
        self.timestamp = timestamp

    def calcular_potencia(self) -> float:
        return self.tensao_v * self.corrente_a

    def validar(self) -> bool:
        if self.tensao_v < 0:
            return False
        if self.corrente_a < 0:
            return False
        return True

    def get_dados(self) -> dict:
        dicionario = {
            "tensao": self.tensao_v,
            "corrente": self.corrente_a,
            "potencia": self.calcular_potencia(),
            "data_hora": self.timestamp.strftime("%d/%m/%Y %H:%M:%S"),
        }
        return dicionario
