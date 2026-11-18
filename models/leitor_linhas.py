class LeitorLinhas:
    """Junta os bytes que chegam da porta serial e devolve as linhas completas.

    Cada leitura da porta devolve o que estiver no buffer, e isso pode terminar no meio
    de um pacote: o pedaço sem \\n fica guardado até o resto chegar. Bytes que não são
    ASCII (o lixo da troca de taxa, por exemplo) viram o caractere de substituição
    (U+FFFD), e a linha é recusada depois pelo protocolo. Sem Qt e sem pyserial: só
    trabalha com bytes.
    """

    # Um pacote $DAT tem uns 22 caracteres e a maior linha do firmware, uns 60. Um
    # pedaço maior sem \n é lixo de taxa errada e é jogado fora.
    TAMANHO_MAXIMO = 256

    def __init__(self, tamanho_maximo=TAMANHO_MAXIMO):
        self.tamanho_maximo = tamanho_maximo
        self._buffer = bytearray()
        self.descartados = 0  # pedaços jogados fora por passar do tamanho máximo

    def adicionar(self, dados: bytes) -> list:
        """Inclui os bytes lidos e devolve as linhas que se completaram (sem o \\r\\n)."""
        self._buffer.extend(dados)
        linhas = []
        while True:
            fim = self._buffer.find(b"\n")
            if fim < 0:
                break
            bruta = bytes(self._buffer[:fim])
            del self._buffer[:fim + 1]
            linhas.append(bruta.decode("ascii", errors="replace").rstrip("\r"))

        if len(self._buffer) > self.tamanho_maximo:
            self._buffer.clear()
            self.descartados += 1
        return linhas

    def limpar(self):
        """Esquece o pedaço guardado, por exemplo depois de trocar a taxa da porta."""
        self._buffer.clear()
