import json
import logging
import os

logger = logging.getLogger("smartgrid")

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigManager:
    """Configurações da aplicação persistidas em data/config.json.

    O arquivo é lido uma única vez e os valores ficam em memória:
    get() consulta a memória e set() altera a memória e regrava o arquivo.
    """

    PASTA_DATA = os.path.join(PASTA_PROJETO, "data")
    CAMINHO = os.path.join(PASTA_DATA, "config.json")

    DEFAULTS = {
        "porta_com": "COM1",
        "baud_rate": 9600,
        "corrente_max": 25.0,
        "tensao_desarme": 242.0,
    }

    _dados = None

    @classmethod
    def carregar(cls):
        """Lê o config.json. Chaves que faltarem no arquivo recebem o valor default."""
        if not os.path.exists(cls.CAMINHO):
            cls._dados = dict(cls.DEFAULTS)
            return

        with open(cls.CAMINHO, encoding="utf-8") as arquivo:
            lidos = json.load(arquivo)

        cls._dados = {**cls.DEFAULTS, **lidos}
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
    def _salvar(cls):
        try:
            os.makedirs(cls.PASTA_DATA, exist_ok=True)
            with open(cls.CAMINHO, "w", encoding="utf-8") as arquivo:
                json.dump(cls._dados, arquivo, indent=4, ensure_ascii=False)
        except OSError as erro:
            logger.error("Não foi possível salvar o config.json: %s", erro)
