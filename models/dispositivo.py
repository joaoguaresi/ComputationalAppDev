from datetime import datetime


class Dispositivo:
    """Equipamento de manobra cadastrado na tabela dispositivos do banco."""

    DISJUNTOR = "DISJUNTOR"
    RELE = "RELE"

    ABERTO = "ABERTO"
    FECHADO = "FECHADO"

    TAG_DISJUNTOR_PRINCIPAL = "DJ-PRINCIPAL"
    TAG_RELE_EMERGENCIA = "RL-EMERGENCIA"

    def __init__(self, tag, tipo, status=FECHADO, ultima_atualizacao=None, dispositivo_id=None):
        self.id = dispositivo_id
        self.tag = tag
        self.tipo = tipo
        self.status = status

        if ultima_atualizacao is None:
            ultima_atualizacao = datetime.now()
        self.ultima_atualizacao = ultima_atualizacao
