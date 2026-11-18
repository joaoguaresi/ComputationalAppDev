"""Placa simulada para os testes da thread serial.

Imita o firmware do professor atrás da mesma interface de uma porta do pyserial
(read, write, in_waiting, baudrate, close), para os testes rodarem sem o Arduino.
Abrir a porta reinicia a placa, como o DTR faz com o Uno de verdade.
"""

import threading
import time

import serial

from models.protocolo import (
    FREQUENCIA_AMOSTRAGEM_HZ,
    PREFIXO_ACK_TAXA,
    SUFIXO_ACK_TAXA,
    TAXA_INICIAL,
    TAXAS_SUPORTADAS,
    TEXTO_BANNER,
    TEXTO_ERR_TAXA,
    montar_pacote_dados,
)

# Banner do firmware, igual ao do manual.
LINHAS_BANNER = (
    "========================================",
    TEXTO_BANNER,
    "Envie !S115200 para iniciar nessa taxa",
    "Envie !P para pausar e voltar para 9600",
    "========================================",
)


class PlacaSimulada:
    def __init__(self, enviar_banner=True, atraso_banner_s=0.05, responder_taxa=True, recusar_taxa=False,
                 a0=512, a1=512, rele_ao_ligar=0):
        self.enviar_banner = enviar_banner
        self.atraso_banner_s = atraso_banner_s
        self.responder_taxa = responder_taxa
        self.recusar_taxa = recusar_taxa
        self.rele_ao_ligar = rele_ao_ligar
        self.transmitir_apos_ack = True

        # Entradas da placa: os testes mudam estes valores a qualquer momento.
        self.a0 = a0
        self.a1 = a1
        self.rele = rele_ao_ligar
        self.botao = 0
        self.transmitindo = False
        self._inicio_transmissao = None
        self._pacotes_enviados = 0

        self._trava = threading.Lock()
        self._saida = []      # pedaços (taxa em que a placa enviou, bytes) ainda não lidos
        self.comandos = []    # tudo o que o desktop escreveu, na ordem
        self.momentos_comandos = []
        self.timeout = 0.02

        self.taxa_placa = TAXA_INICIAL
        self._banner_em = None
        self.banner_enviado_em = None

        self.cabo_conectado = True
        self.aberta = False
        self.aberturas = 0
        self.baudrate = TAXA_INICIAL  # taxa do lado do desktop: o worker muda este valor

    # ------------------------------------------------------------------
    # Fábrica usada pelo SerialWorker no lugar de serial.Serial
    # ------------------------------------------------------------------

    def abrir(self, porta):
        if not self.cabo_conectado:
            raise serial.SerialException(
                f"could not open port '{porta}': FileNotFoundError(2, 'O sistema não pode encontrar o arquivo especificado.')"
            )
        with self._trava:
            self.aberturas += 1
            self.aberta = True
            self.baudrate = TAXA_INICIAL
            self._reiniciar()
        return self

    def _reiniciar(self):
        """O Uno reiniciando: volta a 9600 e, passado o bootloader, manda o banner."""
        self._saida.clear()
        self.taxa_placa = TAXA_INICIAL
        self.transmitindo = False
        self.rele = self.rele_ao_ligar
        self._banner_em = time.monotonic() + self.atraso_banner_s if self.enviar_banner else None

    # ------------------------------------------------------------------
    # Interface de porta do pyserial
    # ------------------------------------------------------------------

    @property
    def in_waiting(self):
        self._conferir_cabo()
        with self._trava:
            self._gerar()
            return sum(len(pedaco) for _, pedaco in self._saida)

    def read(self, tamanho=1):
        self._conferir_cabo()
        limite = time.monotonic() + self.timeout
        while time.monotonic() < limite:
            with self._trava:
                self._gerar()
                if self._saida:
                    return self._entregar(tamanho)
            time.sleep(0.002)
        return b""

    def write(self, dados):
        self._conferir_cabo()
        texto = dados.decode("ascii")
        with self._trava:
            self.comandos.append(texto)
            self.momentos_comandos.append(time.monotonic())
            self._executar(texto.strip())
        return len(dados)

    def reset_input_buffer(self):
        with self._trava:
            self._gerar()
            self._saida.clear()

    def close(self):
        self.aberta = False

    def _conferir_cabo(self):
        # Mensagem igual à do pyserial no Windows quando o USB é puxado.
        if not self.cabo_conectado:
            raise serial.SerialException("ClearCommError failed (PermissionError(13, 'O dispositivo não reconhece o comando.'))")

    # ------------------------------------------------------------------
    # Ações dos testes
    # ------------------------------------------------------------------

    def puxar_cabo(self):
        self.cabo_conectado = False

    def religar_cabo(self):
        self.cabo_conectado = True

    def silenciar(self):
        """A placa trava: a porta continua aberta, mas nada mais chega."""
        with self._trava:
            self.transmitindo = False

    def injetar(self, texto):
        """Coloca uma linha qualquer no fio, por exemplo um pacote com checksum errado."""
        with self._trava:
            self._enviar(texto)

    # ------------------------------------------------------------------
    # Firmware: resposta aos comandos
    # ------------------------------------------------------------------

    def _executar(self, comando):
        if comando.startswith("!S"):
            self._iniciar(comando[2:])

    def _iniciar(self, taxa_pedida):
        """!S<taxa>: responde na taxa atual e só depois passa para a nova."""
        if not self.responder_taxa:
            return
        taxa = int(taxa_pedida) if taxa_pedida.isdigit() else None
        if self.recusar_taxa or taxa not in TAXAS_SUPORTADAS:
            self._enviar(TEXTO_ERR_TAXA)
            return
        self._enviar(f"{PREFIXO_ACK_TAXA}{taxa}{SUFIXO_ACK_TAXA}")
        self.taxa_placa = taxa
        self.transmitindo = self.transmitir_apos_ack
        self._inicio_transmissao = time.monotonic()
        self._pacotes_enviados = 0

    # ------------------------------------------------------------------
    # Saída da placa
    # ------------------------------------------------------------------

    def _enviar(self, texto):
        self._saida.append((self.taxa_placa, (texto + "\r\n").encode("ascii")))

    def _gerar(self):
        """Coloca no fio o que a placa já teria enviado até agora."""
        agora = time.monotonic()
        if self._banner_em is not None and agora >= self._banner_em:
            self._banner_em = None
            self.banner_enviado_em = agora
            for linha in LINHAS_BANNER:
                self._enviar(linha)

        if self.transmitindo:
            # Timer1 do firmware: um pacote a cada 5 ms.
            devidos = int((agora - self._inicio_transmissao) * FREQUENCIA_AMOSTRAGEM_HZ) - self._pacotes_enviados
            for _ in range(min(devidos, 100)):
                self._enviar(montar_pacote_dados(self.a0, self.a1, self.rele, self.botao))
            self._pacotes_enviados += max(devidos, 0)

    def _entregar(self, tamanho):
        """Bytes enviados numa taxa diferente da porta do desktop chegam como lixo."""
        saida = bytearray()
        while self._saida and len(saida) < tamanho:
            taxa, pedaco = self._saida[0]
            falta = tamanho - len(saida)
            parte = pedaco[:falta]
            saida += parte if taxa == self.baudrate else b"\xf0" * len(parte)
            if len(pedaco) > falta:
                self._saida[0] = (taxa, pedaco[falta:])
            else:
                self._saida.pop(0)
        return bytes(saida)
