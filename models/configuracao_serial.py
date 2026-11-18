from serial.tools import list_ports

from models.protocolo import TAXA_PADRAO, TAXAS_SUPORTADAS


class ConfiguracaoSerial:
    """Conexão com a placa escolhida no painel serial: porta, taxa e timeout.

    A porta sempre abre em 9600 bps, a taxa em que a placa liga. A taxa escolhida no
    painel é a que o desktop pede no handshake (!S<taxa>), 115200 por padrão: das
    quatro, é a única que dá conta dos 200 pacotes por segundo do firmware.
    """

    BAUD_RATES = list(TAXAS_SUPORTADAS)
    BAUD_RATE_PADRAO = TAXA_PADRAO

    TIMEOUT_PADRAO = 1000
    TIMEOUT_MINIMO = 100
    TIMEOUT_MAXIMO = 10000

    # Estados da máquina do SerialWorker, na ordem do handshake com a placa.
    DESCONECTADO = "DESCONECTADO"    # porta fechada
    CONECTANDO = "CONECTANDO"        # porta aberta em 9600, esperando o banner do reset do Uno
    NEGOCIANDO = "NEGOCIANDO"        # !S<taxa> enviado, esperando o ACK ou o ERR (ainda em 9600)
    CALIBRANDO = "CALIBRANDO"        # porta já na taxa nova, medindo o zero da corrente
    CONECTADO = "CONECTADO"          # telemetria $DAT chegando
    RECONECTANDO = "RECONECTANDO"    # conexão perdida (cabo puxado ou silêncio), tentando de novo
    DESCONECTANDO = "DESCONECTANDO"  # !P enviado, fechando a porta

    ESTADOS = (DESCONECTADO, CONECTANDO, NEGOCIANDO, CALIBRANDO, CONECTADO, RECONECTANDO, DESCONECTANDO)

    def __init__(self, porta="", baud_rate=None, timeout_ms=None):
        if baud_rate is None:
            baud_rate = ConfiguracaoSerial.BAUD_RATE_PADRAO
        if timeout_ms is None:
            timeout_ms = ConfiguracaoSerial.TIMEOUT_PADRAO

        self.porta = porta
        self.baud_rate = baud_rate
        self.timeout_ms = timeout_ms
        self.estado = ConfiguracaoSerial.DESCONECTADO

    @staticmethod
    def listar_portas() -> list:
        """Portas seriais presentes no computador, pelo pyserial (ex.: ['COM3', 'COM5'])."""
        portas = [porta.device for porta in list_ports.comports()]
        # COM10 depois de COM9, e não entre COM1 e COM2.
        return sorted(portas, key=lambda nome: (len(nome), nome))

    def esta_conectado(self) -> bool:
        return self.estado == ConfiguracaoSerial.CONECTADO

    def validar(self) -> bool:
        if not self.porta:
            return False
        if self.baud_rate not in ConfiguracaoSerial.BAUD_RATES:
            return False
        if self.timeout_ms < ConfiguracaoSerial.TIMEOUT_MINIMO:
            return False
        if self.timeout_ms > ConfiguracaoSerial.TIMEOUT_MAXIMO:
            return False
        return True

    def conectar(self) -> bool:
        """Conexão simulada: até a thread serial existir, só muda o status visual do painel."""
        if not self.validar():
            return False
        self.estado = ConfiguracaoSerial.CONECTADO
        return True

    def desconectar(self):
        self.estado = ConfiguracaoSerial.DESCONECTADO

    def get_texto_status(self) -> str:
        if self.esta_conectado():
            return f"CONECTADO: {self.porta} @ {self.baud_rate} bps"
        return "DESCONECTADO"

    def get_cor_status(self) -> str:
        if self.esta_conectado():
            return "#2ECC71"
        return "#7F8C8D"

    def get_dados(self) -> dict:
        dicionario = {
            "porta": self.porta,
            "baud_rate": self.baud_rate,
            "timeout_ms": self.timeout_ms,
            "estado": self.estado,
            "texto": self.get_texto_status(),
            "cor": self.get_cor_status(),
        }
        return dicionario
