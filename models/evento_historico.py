from datetime import datetime

from models.dispositivo import Dispositivo


class EventoHistorico:
    """Ocorrência do histórico de eventos, gravada na tabela eventos do banco."""

    CORTE_EMERGENCIA = "Corte de Emergência"
    MUDANCA_DISJUNTOR = "Mudança de Estado do Disjuntor"
    LIMITE_EXCEDIDO = "Limite Excedido"
    REGRAS_ALERTA = "Regras de Alerta"
    CONEXAO_SERIAL = "Conexão Serial"
    RELE_ESPONTANEO = "Mudança Espontânea do Relé"
    BOTAO_LOCAL = "Botão Local"

    def __init__(self, tipo, descricao, valor=None, unidade="", timestamp=None,
                 dispositivo_tag=None, evento_id=None):
        self.id = evento_id
        self.tipo = tipo
        self.descricao = descricao
        self.valor = valor
        self.unidade = unidade

        # Tag do dispositivo envolvido (ex.: DJ-PRINCIPAL), ou None quando o evento
        # não pertence a nenhum dispositivo.
        self.dispositivo_tag = dispositivo_tag

        if timestamp is None:
            timestamp = datetime.now()
        self.timestamp = timestamp

    @classmethod
    def rele_espontaneo(cls, status_rele, timestamp=None):
        """Relé que mudou sem comando do operador (RastreadorRele.ESPONTANEO), por exemplo
        o Uno reiniciando com o relé desligado.

        Usa o STATUS_RELE como o firmware manda (1 = ligado). O LED da bancada acende ao
        contrário, porque a saída é active-low, mas isso não muda o valor do protocolo.
        """
        estado = "LIGADO" if status_rele == 1 else "DESLIGADO"
        return cls(
            cls.RELE_ESPONTANEO,
            f"Relé de emergência passou a {estado} sem comando do operador",
            timestamp=timestamp,
            dispositivo_tag=Dispositivo.TAG_RELE_EMERGENCIA,
        )

    @classmethod
    def botao_local(cls, timestamp=None):
        """Aperto confirmado do botão da bancada (pino 11), o disparo local do disjuntor."""
        return cls(
            cls.BOTAO_LOCAL,
            "Botão local da bancada pressionado: disparo do disjuntor solicitado",
            timestamp=timestamp,
            dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
        )

    def get_data_hora(self) -> str:
        return self.timestamp.strftime("%d/%m/%Y %H:%M:%S")

    def get_valor_formatado(self) -> str:
        if self.valor is None:
            return "-"
        return f"{self.valor:.2f} {self.unidade}".strip()

    def get_linha_tabela(self) -> list:
        lista = [
            self.get_data_hora(),
            self.tipo,
            self.descricao,
            self.get_valor_formatado(),
        ]
        return lista
