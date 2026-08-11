from datetime import datetime


class EventoHistorico:
    CORTE_EMERGENCIA = "Corte de Emergência"
    MUDANCA_DISJUNTOR = "Mudança de Estado do Disjuntor"
    LIMITE_EXCEDIDO = "Limite Excedido"

    def __init__(self, tipo, descricao, valor=None, unidade="", timestamp=None):
        self.tipo = tipo
        self.descricao = descricao
        self.valor = valor
        self.unidade = unidade

        if timestamp is None:
            timestamp = datetime.now()
        self.timestamp = timestamp

    def get_data_hora(self) -> str:
        return self.timestamp.strftime("%d/%m/%Y %H:%M:%S")

    def get_valor_formatado(self) -> str:
        if self.valor is None:
            return "-"
        return f"{self.valor:.2f} {self.unidade}".strip()

    def get_linha_tabela(self) -> list:
        lista = [
            self.get_data_hora(),
            self.tipo,
            self.descricao,
            self.get_valor_formatado(),
        ]
        return lista
