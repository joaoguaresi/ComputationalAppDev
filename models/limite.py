from models.dispositivo import Dispositivo


class Limite:
    """Limite de segurança gravado na tabela limites do banco.

    Cada parâmetro tem um único limite (coluna parametro UNIQUE). A medição viola o
    limite quando fica acima do valor configurado: corrente acima da máxima ou tensão
    acima da tensão de desarme.
    """

    CORRENTE_MAX = "CORRENTE_MAX"
    TENSAO_DESARME = "TENSAO_DESARME"

    PARAMETROS = (CORRENTE_MAX, TENSAO_DESARME)

    UNIDADES = {
        CORRENTE_MAX: "A",
        TENSAO_DESARME: "V",
    }

    # Nome exibido no QDialog de limites e no histórico.
    NOMES = {
        CORRENTE_MAX: "Corrente máxima",
        TENSAO_DESARME: "Tensão de desarme",
    }

    # Grandeza medida, usada na mensagem de violação ("Limite de corrente violado").
    GRANDEZAS = {
        CORRENTE_MAX: "corrente",
        TENSAO_DESARME: "tensão",
    }

    def __init__(self, parametro, valor, unidade=None,
                 dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL, limite_id=None):
        self.id = limite_id
        self.parametro = parametro
        self.valor = valor

        if unidade is None:
            unidade = Limite.UNIDADES[parametro]
        self.unidade = unidade

        # Tag do dispositivo protegido pelo limite, ou None quando ele não pertence a
        # nenhum dispositivo. Os dois limites atuam sobre o disjuntor principal: é ele
        # que abre quando a corrente ou a tensão passam do limite.
        self.dispositivo_tag = dispositivo_tag

    def extrair_valor(self, medicao) -> float:
        """Valor da medição que é comparado com este limite."""
        if self.parametro == Limite.CORRENTE_MAX:
            return medicao.corrente_a
        return medicao.tensao_v

    def foi_violado(self, valor_medido) -> bool:
        return valor_medido > self.valor

    def get_nome(self) -> str:
        return Limite.NOMES[self.parametro]

    def get_grandeza(self) -> str:
        return Limite.GRANDEZAS[self.parametro]

    def get_valor_formatado(self) -> str:
        return f"{self.valor:.2f} {self.unidade}"
