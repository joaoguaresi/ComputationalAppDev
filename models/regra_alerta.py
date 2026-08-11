class RegraAlerta:
    TENSAO = "TENSAO"
    CORRENTE = "CORRENTE"
    POTENCIA = "POTENCIA"

    UNIDADES = {
        TENSAO: "V",
        CORRENTE: "A",
        POTENCIA: "W",
    }

    def __init__(self, grandeza, limite_max, limite_min=None, descricao=""):
        self.grandeza = grandeza
        self.limite_max = limite_max
        self.limite_min = limite_min
        self.descricao = descricao
        self.ativa = True

    def validar_limites(self) -> bool:
        if self.limite_min is None:
            return True
        return self.limite_min < self.limite_max

    def foi_violada(self, valor) -> bool:
        if not self.ativa:
            return False
        if valor > self.limite_max:
            return True
        if self.limite_min is not None and valor < self.limite_min:
            return True
        return False

    def avaliar(self, medicao) -> bool:
        if self.grandeza == RegraAlerta.TENSAO:
            valor = medicao.tensao_v
        elif self.grandeza == RegraAlerta.CORRENTE:
            valor = medicao.corrente_a
        else:
            valor = medicao.calcular_potencia()
        return self.foi_violada(valor)

    def get_unidade(self) -> str:
        return RegraAlerta.UNIDADES[self.grandeza]

    def get_dados(self) -> dict:
        dicionario = {
            "grandeza": self.grandeza,
            "limite_max": self.limite_max,
            "limite_min": self.limite_min,
            "descricao": self.descricao,
            "unidade": self.get_unidade(),
            "ativa": self.ativa,
        }
        return dicionario
