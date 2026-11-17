"""Protocolo serial do firmware do professor (codigo_arduino.ino).

O firmware não pode ser alterado: os textos abaixo foram copiados do manual e do
código da placa, caractere por caractere. Este módulo só trabalha com texto, sem Qt
e sem pyserial, para servir ao SerialWorker e aos testes sem precisar da placa.
"""


class ProtocoloError(ValueError):
    """Linha da placa fora do protocolo: checksum errado, campo faltando ou valor inválido."""


# Taxas aceitas pelo comando !S. A placa sempre liga (e volta do !P) em 9600.
TAXAS_SUPORTADAS = (9600, 19200, 38400, 115200)
TAXA_INICIAL = 9600
TAXA_PADRAO = 115200

# Timer1 do firmware: 16 MHz / (64 x 1250) = 200 amostras por segundo.
FREQUENCIA_AMOSTRAGEM_HZ = 200

# O ADC do Arduino Uno lê de 0 a 1023.
ADC_MAXIMO = 1023

# Pacote de telemetria: $DAT,<A0>,<A1>,<STATUS_RELE>,<STATUS_BOTAO>*<CHECKSUM>
INICIO_PACOTE = "$"
SEPARADOR_CHECKSUM = "*"
IDENTIFICADOR_DADOS = "DAT"

# Linhas que a placa envia.
TEXTO_BANNER = "PLACA EM ESPERA (9600 baud)"
PREFIXO_ACK_TAXA = ">>> ACK: INICIANDO EM "
SUFIXO_ACK_TAXA = " BPS <<<"
TEXTO_ACK_PAUSA = ">>> ACK: CONVERSAO PAUSADA. RETORNANDO A 9600 BPS <<<"
TEXTO_ACK_RELE_LIGADO = ">>> ACK: RELE LIGADO <<<"
TEXTO_ACK_RELE_DESLIGADO = ">>> ACK: RELE DESLIGADO <<<"
TEXTO_ACK_RELE_ALTERNADO = ">>> ACK: RELE ALTERNADO <<<"
TEXTO_ERR_TAXA = ">>> ERR: BAUD INVALIDO. Use 9600, 19200, 38400 ou 115200 <<<"

# Comandos enviados pelo desktop: começam com ! e terminam em \n.
COMANDO_PAUSA = "!P\n"
COMANDO_RELE_LIGA = "!1\n"
COMANDO_RELE_DESLIGA = "!0\n"
COMANDO_RELE_ALTERNA = "!T\n"


def montar_comando_taxa(taxa: int) -> str:
    """Comando do handshake. Ex.: montar_comando_taxa(115200) devolve '!S115200\\n'."""
    if taxa not in TAXAS_SUPORTADAS:
        raise ProtocoloError(f"taxa {taxa} não suportada; use uma destas: {TAXAS_SUPORTADAS}")
    return f"!S{taxa}\n"


def calcular_checksum(payload: str) -> str:
    """XOR de todos os caracteres entre $ e * (nenhum dos dois entra), em 2 dígitos hex maiúsculos."""
    resultado = 0
    for caractere in payload:
        resultado ^= ord(caractere)
    return f"{resultado:02X}"


def montar_pacote_dados(a0: int, a1: int, status_rele: int, status_botao: int) -> str:
    """Monta um pacote $DAT igual ao do firmware, sem o \\r\\n do fim. Usado nos testes."""
    payload = f"{IDENTIFICADOR_DADOS},{a0},{a1},{status_rele},{status_botao}"
    return f"{INICIO_PACOTE}{payload}{SEPARADOR_CHECKSUM}{calcular_checksum(payload)}"
