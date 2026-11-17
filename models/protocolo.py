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


def validar_pacote(linha: str):
    """
    Valida um pacote serial no formato $DAT,...*XX
    Retorna uma tupla (sucesso: bool, payload: str)
    """
    # Função copiada sem mudanças do manual da placa.
    linha = linha.strip()

    # 1. Verifica se contém os delimitadores obrigatórios
    if not linha.startswith('$') or '*' not in linha:
        return False, None

    # 2. Divide entre a carga útil e o checksum recebido
    # Ex: '$DAT,512,716,1,0*2C' -> payload = 'DAT,512,716,1,0', checksum_recebido = '2C'
    payload, checksum_recebido = linha[1:].split('*', 1)

    # 3. Calcula o XOR acumulado dos caracteres do payload
    checksum_calculado = 0
    for caractere in payload:
        checksum_calculado ^= ord(caractere)

    # 4. Formata o valor calculado em Hexadecimal com 2 dígitos maiúsculos (ex: '2C' ou '0A')
    checksum_formatado = f"{checksum_calculado:02X}"

    # 5. Compara o checksum calculado com o recebido
    if checksum_formatado == checksum_recebido.upper():
        return True, payload
    else:
        return False, None


class LinhaSerial:
    """Uma linha recebida da placa, já classificada pelo tipo.

    Os ACKs dos comandos chegam no meio dos pacotes $DAT, então cada linha é
    reconhecida pelo começo. Em DADOS, valor é um dicionário com a0, a1,
    status_rele e status_botao; em ACK_TAXA, é a taxa confirmada.
    """

    BANNER = "BANNER"
    INFORMATIVA = "INFORMATIVA"  # demais linhas do banner ("====" e "Envie ...")
    VAZIA = "VAZIA"
    ACK_TAXA = "ACK_TAXA"
    ACK_PAUSA = "ACK_PAUSA"
    ACK_RELE_LIGADO = "ACK_RELE_LIGADO"
    ACK_RELE_DESLIGADO = "ACK_RELE_DESLIGADO"
    ACK_RELE_ALTERNADO = "ACK_RELE_ALTERNADO"
    ERR_TAXA = "ERR_TAXA"
    DADOS = "DADOS"
    DESCONHECIDA = "DESCONHECIDA"

    def __init__(self, tipo, texto, valor=None):
        self.tipo = tipo
        self.texto = texto
        self.valor = valor


_TEXTOS_FIXOS = {
    TEXTO_BANNER: LinhaSerial.BANNER,
    TEXTO_ACK_PAUSA: LinhaSerial.ACK_PAUSA,
    TEXTO_ACK_RELE_LIGADO: LinhaSerial.ACK_RELE_LIGADO,
    TEXTO_ACK_RELE_DESLIGADO: LinhaSerial.ACK_RELE_DESLIGADO,
    TEXTO_ACK_RELE_ALTERNADO: LinhaSerial.ACK_RELE_ALTERNADO,
    TEXTO_ERR_TAXA: LinhaSerial.ERR_TAXA,
}


def interpretar_linha(linha: str) -> LinhaSerial:
    """Classifica uma linha da placa. Lança ProtocoloError para um $DAT inválido."""
    texto = linha.strip()

    if not texto:
        return LinhaSerial(LinhaSerial.VAZIA, texto)
    if texto.startswith(INICIO_PACOTE):
        return LinhaSerial(LinhaSerial.DADOS, texto, _decodificar_dados(texto))
    if texto in _TEXTOS_FIXOS:
        return LinhaSerial(_TEXTOS_FIXOS[texto], texto)
    if texto.startswith(PREFIXO_ACK_TAXA) and texto.endswith(SUFIXO_ACK_TAXA):
        return LinhaSerial(LinhaSerial.ACK_TAXA, texto, _ler_taxa_do_ack(texto))
    if texto.startswith("=") or texto.startswith("Envie"):
        return LinhaSerial(LinhaSerial.INFORMATIVA, texto)
    return LinhaSerial(LinhaSerial.DESCONHECIDA, texto)


def _ler_taxa_do_ack(texto: str) -> int:
    numero = texto[len(PREFIXO_ACK_TAXA):-len(SUFIXO_ACK_TAXA)]
    try:
        return int(numero)
    except ValueError as erro:
        raise ProtocoloError(f"taxa ilegível no ACK: {texto!r}") from erro


def _decodificar_dados(texto: str) -> dict:
    valido, payload = validar_pacote(texto)
    if not valido:
        raise ProtocoloError(f"checksum inválido: {texto!r}")

    campos = payload.split(",")
    if len(campos) != 5 or campos[0] != IDENTIFICADOR_DADOS:
        raise ProtocoloError(f"pacote fora do formato $DAT,A0,A1,RELE,BOTAO: {texto!r}")

    try:
        a0, a1, status_rele, status_botao = (int(campo) for campo in campos[1:])
    except ValueError as erro:
        raise ProtocoloError(f"campo não numérico: {texto!r}") from erro

    if not (0 <= a0 <= ADC_MAXIMO and 0 <= a1 <= ADC_MAXIMO):
        raise ProtocoloError(f"leitura do ADC fora de 0 a {ADC_MAXIMO}: {texto!r}")
    if status_rele not in (0, 1) or status_botao not in (0, 1):
        raise ProtocoloError(f"status do relé ou do botão diferente de 0 e 1: {texto!r}")

    return {"a0": a0, "a1": a1, "status_rele": status_rele, "status_botao": status_botao}
