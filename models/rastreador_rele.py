from models.protocolo import (
    COMANDO_RELE_ALTERNA,
    COMANDO_RELE_DESLIGA,
    COMANDO_RELE_LIGA,
    LinhaSerial,
)

_ACKS_DO_RELE = (
    LinhaSerial.ACK_RELE_LIGADO,
    LinhaSerial.ACK_RELE_DESLIGADO,
    LinhaSerial.ACK_RELE_ALTERNADO,
)


class RastreadorRele:
    """Acompanha o relé pelo STATUS_RELE da telemetria.

    O STATUS_RELE é a fonte da verdade (o firmware lê o próprio pino de saída). Com
    ele o rastreador separa três situações:

    - CONFIRMADO: o comando do operador chegou (ACK) e o STATUS_RELE ficou no valor pedido;
    - EXPIRADO: o comando não se confirmou dentro do prazo;
    - ESPONTANEO: o STATUS_RELE mudou sem nenhum comando pendente, por exemplo o Uno
      reiniciando com o relé desligado.

    O tempo vem de fora (agora = time.monotonic()), para o teste não depender do relógio.
    """

    NADA = "NADA"
    INICIAL = "INICIAL"
    CONFIRMADO = "CONFIRMADO"
    EXPIRADO = "EXPIRADO"
    ESPONTANEO = "ESPONTANEO"

    PRAZO_PADRAO_S = 2.0

    def __init__(self, prazo_s=PRAZO_PADRAO_S):
        self.prazo_s = prazo_s
        self.estado = None  # último STATUS_RELE conhecido; None antes da primeira leitura
        self._limpar_pendente()

    @property
    def tem_comando_pendente(self) -> bool:
        return self._alvo is not None

    def comando_enviado(self, comando, agora):
        """Registra o !1, !0 ou !T que acabou de ser enviado à placa."""
        if comando == COMANDO_RELE_LIGA:
            alvo = 1
        elif comando == COMANDO_RELE_DESLIGA:
            alvo = 0
        elif comando == COMANDO_RELE_ALTERNA:
            if self.estado is None:
                raise ValueError("o estado do relé ainda é desconhecido; não dá para alternar")
            alvo = 1 - self.estado
        else:
            raise ValueError(f"comando de relé desconhecido: {comando!r}")

        self._alvo = alvo
        self._enviado_em = agora
        self._ack_recebido = False

    def ack_recebido(self, tipo_linha):
        """Marca o ACK do relé (um dos tipos ACK_RELE_* de LinhaSerial) vindo da placa."""
        if self.tem_comando_pendente and tipo_linha in _ACKS_DO_RELE:
            self._ack_recebido = True

    def atualizar(self, status_rele, agora) -> str:
        """Recebe o STATUS_RELE de cada pacote e devolve o que aconteceu com o relé."""
        if self.estado is None:
            # Primeira leitura depois de conectar: quem chama compara com o estado salvo.
            self.estado = status_rele
            return self.INICIAL

        if self.tem_comando_pendente:
            if self._ack_recebido and status_rele == self._alvo:
                self.estado = status_rele
                self._limpar_pendente()
                return self.CONFIRMADO
            if agora - self._enviado_em > self.prazo_s:
                self.estado = status_rele
                self._limpar_pendente()
                return self.EXPIRADO
            return self.NADA

        if status_rele != self.estado:
            self.estado = status_rele
            return self.ESPONTANEO
        return self.NADA

    def reiniciar(self):
        """Esquece o estado e o comando pendente, por exemplo ao reconectar a placa."""
        self.estado = None
        self._limpar_pendente()

    def _limpar_pendente(self):
        self._alvo = None
        self._enviado_em = None
        self._ack_recebido = False
