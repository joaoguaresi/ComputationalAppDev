"""Placa simulada para os testes da thread serial.

Imita o firmware do professor atrás da mesma interface de uma porta do pyserial
(read, write, in_waiting, baudrate, close), para os testes rodarem sem o Arduino.
Abrir a porta reinicia a placa, como o DTR faz com o Uno de verdade.
"""

import threading
import time

import serial

from models.protocolo import TAXA_INICIAL


class PlacaSimulada:
    def __init__(self):
        self._trava = threading.Lock()
        self._saida = []      # pedaços (taxa em que a placa enviou, bytes) ainda não lidos
        self.comandos = []    # tudo o que o desktop escreveu, na ordem
        self.timeout = 0.02

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
            self._saida.clear()
        return self

    # ------------------------------------------------------------------
    # Interface de porta do pyserial
    # ------------------------------------------------------------------

    @property
    def in_waiting(self):
        with self._trava:
            return sum(len(pedaco) for _, pedaco in self._saida)

    def read(self, tamanho=1):
        limite = time.monotonic() + self.timeout
        while time.monotonic() < limite:
            with self._trava:
                if self._saida:
                    return self._entregar(tamanho)
            time.sleep(0.002)
        return b""

    def write(self, dados):
        with self._trava:
            self.comandos.append(dados.decode("ascii"))
        return len(dados)

    def close(self):
        self.aberta = False

    # ------------------------------------------------------------------
    # Ações dos testes
    # ------------------------------------------------------------------

    def puxar_cabo(self):
        self.cabo_conectado = False

    def religar_cabo(self):
        self.cabo_conectado = True

    # ------------------------------------------------------------------
    # Saída da placa
    # ------------------------------------------------------------------

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
