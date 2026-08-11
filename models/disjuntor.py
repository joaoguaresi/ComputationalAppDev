from datetime import datetime


class Disjuntor:
    FECHADO = "FECHADO"
    ABERTO = "ABERTO"

    def __init__(self):
        self.estado = Disjuntor.FECHADO
        self.ultima_alteracao = datetime.now()

    def abrir(self):
        self.estado = Disjuntor.ABERTO
        self.ultima_alteracao = datetime.now()

    def fechar(self):
        self.estado = Disjuntor.FECHADO
        self.ultima_alteracao = datetime.now()

    def alternar(self):
        if self.esta_fechado():
            self.abrir()
        else:
            self.fechar()

    def esta_fechado(self) -> bool:
        return self.estado == Disjuntor.FECHADO

    def get_texto(self) -> str:
        if self.esta_fechado():
            return "Disjuntor: FECHADO / NORMAL"
        return "Disjuntor: ABERTO / PROTEÇÃO ATIVADA"

    def get_cor(self) -> str:
        if self.esta_fechado():
            return "#2ECC71"
        return "#E74C3C"

    def get_dados(self) -> dict:
        dicionario = {
            "estado": self.estado,
            "texto": self.get_texto(),
            "cor": self.get_cor(),
            "data_hora": self.ultima_alteracao.strftime("%d/%m/%Y %H:%M:%S"),
        }
        return dicionario
