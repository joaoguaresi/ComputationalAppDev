import logging
import math

from models.config_manager import ConfigManager
from models.dispositivo import Dispositivo

logger = logging.getLogger("smartgrid")


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

    # Chave do valor inicial de cada parâmetro no config.json, usado enquanto a tabela
    # limites ainda está vazia.
    CHAVES_CONFIG = {
        CORRENTE_MAX: "corrente_max",
        TENSAO_DESARME: "tensao_desarme",
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

    @classmethod
    def iniciais_do_config(cls) -> list:
        """Limites iniciais lidos do config.json, um para cada parâmetro.

        O config.json pode ser editado à mão: um valor que não seja um número maior que
        zero é trocado pelo padrão do ConfigManager, com WARNING no log.
        """
        limites = []
        for parametro, chave in cls.CHAVES_CONFIG.items():
            valor = ConfigManager.get(chave)
            if not cls._valor_inicial_valido(valor):
                padrao = ConfigManager.DEFAULTS[chave]
                logger.warning(
                    "Valor inicial inválido para '%s' no config.json: %r. Usando o padrão %s.",
                    chave, valor, padrao,
                )
                valor = padrao
            limites.append(cls(parametro, float(valor)))
        return limites

    @staticmethod
    def _valor_inicial_valido(valor) -> bool:
        # No Python, bool é subclasse de int: true/false no JSON não vale como limite.
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return False
        return math.isfinite(valor) and valor > 0

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

    @staticmethod
    def resumir(limites) -> str:
        """Texto dos limites para o log e o histórico, ex.: "corrente máxima 25.00 A, ..."."""
        return ", ".join(f"{limite.get_nome().lower()} {limite.get_valor_formatado()}" for limite in limites)
