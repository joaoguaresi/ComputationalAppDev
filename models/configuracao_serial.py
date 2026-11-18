from serial.tools import list_ports

from models.protocolo import TAXA_PADRAO, TAXAS_SUPORTADAS


class ConfiguracaoSerial:
    """Conexão com a placa escolhida no painel serial: porta, taxa, timeout e estado.

    A porta sempre abre em 9600 bps, a taxa em que a placa liga. A taxa escolhida no
    painel é a que o desktop pede no handshake (!S<taxa>), 115200 por padrão: das
    quatro, é a única que dá conta dos 200 pacotes por segundo do firmware.

    O estado vem do SerialWorker, pela thread da interface; este model só guarda o
    estado e diz o texto e a cor que o painel mostra.
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

    ROTULOS = {
        DESCONECTADO: "DESCONECTADO",
        CONECTANDO: "CONECTANDO",
        NEGOCIANDO: "HANDSHAKE",
        CALIBRANDO: "CALIBRANDO O ZERO",
        CONECTADO: "CONECTADO",
        RECONECTANDO: "CONEXÃO PERDIDA - RECONECTANDO",
        DESCONECTANDO: "DESCONECTANDO",
    }

    CORES = {
        DESCONECTADO: "#7F8C8D",
        CONECTANDO: "#F39C12",
        NEGOCIANDO: "#F39C12",
        CALIBRANDO: "#F39C12",
        CONECTADO: "#2ECC71",
        RECONECTANDO: "#C0392B",
        DESCONECTANDO: "#7F8C8D",
    }

    # VID USB do Arduino e dos conversores USB-serial mais comuns nos clones
    # (Arduino LLC, Arduino SRL, CH340, FTDI e CP210x). No Windows as portas Bluetooth
    # também aparecem como COM; estas ajudam a achar a placa no meio delas.
    VIDS_ARDUINO = ("2341", "2A03", "1A86", "0403", "10C4")

    def __init__(self, porta="", baud_rate=None, timeout_ms=None):
        if baud_rate is None:
            baud_rate = ConfiguracaoSerial.BAUD_RATE_PADRAO
        if timeout_ms is None:
            timeout_ms = ConfiguracaoSerial.TIMEOUT_PADRAO

        self.porta = porta
        self.baud_rate = baud_rate
        self.timeout_ms = timeout_ms
        self.estado = ConfiguracaoSerial.DESCONECTADO
        self.detalhe = ""

    @staticmethod
    def listar_portas() -> list:
        """Portas seriais presentes, pelo pyserial: [(porta, descrição, parece_arduino)]."""
        portas = []
        for info in list_ports.comports():
            vid = f"{info.vid:04X}" if info.vid is not None else ""
            portas.append((info.device, info.description or "", vid in ConfiguracaoSerial.VIDS_ARDUINO))
        # COM10 depois de COM9, e não entre COM1 e COM2.
        return sorted(portas, key=lambda porta: (len(porta[0]), porta[0]))

    @staticmethod
    def descrever_porta(porta, descricao) -> str:
        """Texto do combo, ex.: 'COM5 - USB-SERIAL CH340'."""
        descricao = (descricao or "").replace(f"({porta})", "").strip()
        if not descricao or descricao == "n/a":
            return porta
        return f"{porta} - {descricao}"

    def atualizar_estado(self, estado, detalhe=""):
        self.estado = estado
        self.detalhe = detalhe

    def esta_conectado(self) -> bool:
        return self.estado == ConfiguracaoSerial.CONECTADO

    def esta_desconectado(self) -> bool:
        return self.estado == ConfiguracaoSerial.DESCONECTADO

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

    def get_texto_status(self) -> str:
        rotulo = ConfiguracaoSerial.ROTULOS.get(self.estado, self.estado)
        if self.detalhe:
            return f"{rotulo}: {self.detalhe}"
        return rotulo

    def get_cor_status(self) -> str:
        return ConfiguracaoSerial.CORES.get(self.estado, "#7F8C8D")

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
