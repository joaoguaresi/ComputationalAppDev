class ConfiguracaoSerial:
    PORTAS_SIMULADAS = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8"]
    BAUD_RATES = [9600, 115200]

    TIMEOUT_PADRAO = 1000
    TIMEOUT_MINIMO = 100
    TIMEOUT_MAXIMO = 10000

    DESCONECTADO = "DESCONECTADO"
    CONECTADO = "CONECTADO"

    def __init__(self, porta=None, baud_rate=None, timeout_ms=None):
        if porta is None:
            porta = ConfiguracaoSerial.PORTAS_SIMULADAS[0]
        if baud_rate is None:
            baud_rate = ConfiguracaoSerial.BAUD_RATES[0]
        if timeout_ms is None:
            timeout_ms = ConfiguracaoSerial.TIMEOUT_PADRAO

        self.porta = porta
        self.baud_rate = baud_rate
        self.timeout_ms = timeout_ms
        self.estado = ConfiguracaoSerial.DESCONECTADO

    @staticmethod
    def listar_portas() -> list:
        """Portas disponíveis. Nesta etapa a conexão é apenas visual, então o
        sistema opera com portas simuladas quando o pyserial não está instalado."""
        try:
            from serial.tools import list_ports
        except ImportError:
            return list(ConfiguracaoSerial.PORTAS_SIMULADAS)

        portas = [porta.device for porta in list_ports.comports()]
        if not portas:
            return list(ConfiguracaoSerial.PORTAS_SIMULADAS)
        return portas

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
        """Conexão simulada: nesta etapa só muda o status visual do painel."""
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
