class DetectorBotao:
    """Reconhece o aperto do botão (pino 11) sem os repiques do contato.

    O firmware manda o estado cru do pino a cada 5 ms, sem debounce. Um estado novo
    só vale depois de aparecer em N amostras seguidas (3 amostras = 15 ms), e só a
    passagem de solto para pressionado (borda 0 -> 1) conta como um aperto.
    """

    AMOSTRAS_PADRAO = 3

    def __init__(self, amostras_confirmacao=AMOSTRAS_PADRAO):
        if amostras_confirmacao < 1:
            raise ValueError("o debounce precisa de pelo menos 1 amostra")
        self.amostras_confirmacao = amostras_confirmacao
        self.estado = 0
        self._candidato = 0
        self._repeticoes = 0

    def atualizar(self, status_botao) -> bool:
        """Recebe o STATUS_BOTAO de cada pacote e devolve True só no aperto confirmado."""
        if status_botao == self.estado:
            # Voltou ao estado firme antes de confirmar: era repique.
            self._repeticoes = 0
            return False

        if status_botao != self._candidato:
            self._candidato = status_botao
            self._repeticoes = 0

        self._repeticoes += 1
        if self._repeticoes < self.amostras_confirmacao:
            return False

        self.estado = status_botao
        self._repeticoes = 0
        return self.estado == 1

    def reiniciar(self):
        """Volta ao estado solto, por exemplo ao reconectar a placa."""
        self.estado = 0
        self._candidato = 0
        self._repeticoes = 0
