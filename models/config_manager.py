import json
import logging
import math
import os

from models.protocolo import ADC_MAXIMO, TAXA_PADRAO, TAXAS_SUPORTADAS

logger = logging.getLogger("smartgrid")

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigManager:
    """Configurações da aplicação persistidas em data/config.json.

    O arquivo é lido uma única vez e os valores ficam em memória:
    get() consulta a memória e set() altera a memória e regrava o arquivo.

    O config.json pode ser editado à mão, então cada valor lido passa por uma
    validação de segurança: a bancada trabalha com 0 a 12 V e ±30 A (manual da
    placa), e um limite acima disso nunca dispararia. Valor fora da faixa ou de tipo
    errado volta ao padrão, com WARNING no log, e o arquivo é regravado já corrigido.
    """

    PASTA_DATA = os.path.join(PASTA_PROJETO, "data")
    CAMINHO = os.path.join(PASTA_DATA, "config.json")

    # Faixa física da bancada, do manual: tensão de 0 a 12 V no barramento (acima disso
    # a entrada analógica pode queimar) e corrente de ±30 A no ACS712-30A.
    TENSAO_MAXIMA_V = 12.0
    CORRENTE_MAXIMA_A = 30.0

    DEFAULTS = {
        "porta_com": "COM1",
        # A porta sempre abre em 9600; esta é a taxa pedida à placa no !S<taxa>.
        "baud_rate": TAXA_PADRAO,
        # Limites iniciais abaixo do fundo de escala, para o alarme conseguir disparar.
        "corrente_max": 25.0,
        "tensao_desarme": 11.5,
        # Conversão do ADC (0 a 1023): 0 a 12 V em A0; ACS712-30A em A1 (66 mV/A,
        # zero no meio da escala). Mesmos valores da Calibracao (leitura_telemetria).
        "fator_tensao": TENSAO_MAXIMA_V / ADC_MAXIMO,
        "sensibilidade_corrente": 0.066,
        "zero_corrente_adc": 512.0,
        # Janela da média gravada na tabela leituras (AgregadorLeituras).
        "taxa_amostragem_ms": 500,
    }

    # Faixa aceita para os valores numéricos: mínimo < valor <= máximo.
    FAIXAS = {
        "corrente_max": (0.0, CORRENTE_MAXIMA_A),
        "tensao_desarme": (0.0, TENSAO_MAXIMA_V),
        "fator_tensao": (0.0, math.inf),
        "sensibilidade_corrente": (0.0, math.inf),
        "zero_corrente_adc": (0.0, float(ADC_MAXIMO)),
    }

    _dados = None

    @classmethod
    def carregar(cls):
        """Lê o config.json. Chaves que faltarem no arquivo recebem o valor default."""
        if not os.path.exists(cls.CAMINHO):
            logger.warning("Arquivo config.json não encontrado. Criando com os valores padrão.")
            cls._restaurar_defaults()
            return

        try:
            with open(cls.CAMINHO, encoding="utf-8") as arquivo:
                lidos = json.load(arquivo)
        except (json.JSONDecodeError, UnicodeDecodeError) as erro:
            logger.error("Arquivo config.json corrompido (%s). Restaurando os valores padrão.", erro)
            cls._restaurar_defaults()
            return

        if not isinstance(lidos, dict):
            logger.error("Arquivo config.json não contém um objeto JSON. Restaurando os valores padrão.")
            cls._restaurar_defaults()
            return

        cls._dados = {**cls.DEFAULTS, **lidos}
        faltando = [chave for chave in cls.DEFAULTS if chave not in lidos]
        corrigidos = cls._corrigir_valores_inseguros()
        if faltando:
            logger.info("Chaves acrescentadas ao config.json com o valor padrão: %s.", ", ".join(faltando))
        if faltando or corrigidos:
            cls._salvar()
        logger.info("Configurações carregadas de data/config.json.")

    @classmethod
    def get(cls, chave, default=None):
        if cls._dados is None:
            cls.carregar()
        return cls._dados.get(chave, default)

    @classmethod
    def set(cls, chave, valor):
        if cls._dados is None:
            cls.carregar()
        cls._dados[chave] = valor
        cls._salvar()
        logger.info("Configuração '%s' alterada para %s.", chave, valor)

    @classmethod
    def valor_valido(cls, chave, valor) -> bool:
        """Confere se o valor é seguro para a chave: faixa da bancada, uma das 4 taxas
        ou, nas demais chaves, o mesmo tipo do valor padrão."""
        if chave in cls.FAIXAS:
            minimo, maximo = cls.FAIXAS[chave]
            return cls._eh_numero(valor) and minimo < valor <= maximo
        if chave == "baud_rate":
            return type(valor) is int and valor in TAXAS_SUPORTADAS
        if chave in cls.DEFAULTS:
            # type() em vez de isinstance(): no Python, bool é subclasse de int.
            return type(valor) is type(cls.DEFAULTS[chave])
        return True

    @staticmethod
    def _eh_numero(valor) -> bool:
        # true/false no JSON não vale como número.
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return False
        return math.isfinite(valor)

    @classmethod
    def _corrigir_valores_inseguros(cls) -> bool:
        """Troca pelo padrão os valores inválidos. Devolve True se corrigiu algum."""
        corrigiu = False
        for chave, padrao in cls.DEFAULTS.items():
            valor = cls._dados[chave]
            if cls.valor_valido(chave, valor):
                continue
            logger.warning(
                "Valor inválido ou fora da faixa segura da bancada (0 a %.0f V, ±%.0f A) para '%s' "
                "no config.json: %r. Usando o padrão %r.",
                cls.TENSAO_MAXIMA_V, cls.CORRENTE_MAXIMA_A, chave, valor, padrao,
            )
            cls._dados[chave] = padrao
            corrigiu = True
        return corrigiu

    @classmethod
    def _restaurar_defaults(cls):
        """Volta todas as configurações para o padrão e grava o arquivo."""
        cls._dados = dict(cls.DEFAULTS)
        cls._salvar()

    @classmethod
    def _salvar(cls):
        try:
            os.makedirs(cls.PASTA_DATA, exist_ok=True)
            with open(cls.CAMINHO, "w", encoding="utf-8") as arquivo:
                json.dump(cls._dados, arquivo, indent=4, ensure_ascii=False)
        except OSError as erro:
            logger.error("Não foi possível salvar o config.json: %s", erro)
