import logging
import queue
import threading
import time
from collections import deque

import serial
from PySide6.QtCore import QObject, Signal, Slot

from models.config_manager import ConfigManager
from models.configuracao_serial import ConfiguracaoSerial
from models.leitor_linhas import LeitorLinhas
from models.leitura_telemetria import Calibracao, LeituraTelemetria, MediaMovel
from models.rastreador_rele import RastreadorRele
from models.protocolo import (
    COMANDO_PAUSA,
    COMANDO_RELE_DESLIGA,
    COMANDO_RELE_LIGA,
    TAXA_INICIAL,
    LinhaSerial,
    ProtocoloError,
    interpretar_linha,
    montar_comando_taxa,
)

logger = logging.getLogger("smartgrid")

# Estados da máquina (ConfiguracaoSerial), com nomes curtos para as transições.
DESCONECTADO = ConfiguracaoSerial.DESCONECTADO
CONECTANDO = ConfiguracaoSerial.CONECTANDO
NEGOCIANDO = ConfiguracaoSerial.NEGOCIANDO
CALIBRANDO = ConfiguracaoSerial.CALIBRANDO
CONECTADO = ConfiguracaoSerial.CONECTADO
RECONECTANDO = ConfiguracaoSerial.RECONECTANDO
DESCONECTANDO = ConfiguracaoSerial.DESCONECTANDO


class FalhaConexaoError(Exception):
    """A conexão não foi estabelecida: porta que não abre ou placa que não responde."""


class ConexaoInterrompidaError(Exception):
    """O operador pediu para desconectar, ou a aplicação está fechando, no meio de uma espera."""


def abrir_porta_serial(porta):
    """Abre a porta de verdade, sempre em 9600 bps, a taxa em que a placa liga.

    Abrir a porta mexe no DTR, e o Arduino Uno reinicia: é por isso que a placa manda
    o banner logo depois. Os testes trocam esta função por uma placa simulada.
    """
    return serial.Serial(
        porta,
        TAXA_INICIAL,
        timeout=SerialWorker.TIMEOUT_LEITURA_S,
        write_timeout=SerialWorker.TIMEOUT_ESCRITA_S,
    )


class SerialWorker(QObject):
    """Comunicação com a placa fora da thread da interface.

    O SerialController move o worker para uma QThread (moveToThread) e liga o started
    dela ao executar(). O executar() é um laço que ocupa a thread do começo ao fim: a
    cada volta ele atende a fila de comandos, lê o que chegou na porta e avança a
    máquina de estados. Tudo o que bloqueia (abrir a porta, ler e escrever) acontece
    aqui, nunca na thread da interface.

    Fila de comandos: como o laço não devolve o controle ao Qt, um slot chamado por
    sinal enfileirado só rodaria depois do fim da thread. Por isso a interface faz os
    pedidos pelos métodos pedir_*, que só colocam o pedido numa queue.Queue (segura
    entre threads) e voltam na hora; o laço atende a fila na ordem de chegada. As
    respostas saem por sinais, que o Qt entrega na thread da interface.

    Máquina de estados (constantes em ConfiguracaoSerial):

        DESCONECTADO --conectar--> CONECTANDO --banner--> NEGOCIANDO --ACK--> CALIBRANDO --> CONECTADO
        CONECTADO --cabo puxado ou silêncio--> RECONECTANDO --porta voltou--> CONECTANDO
        qualquer estado --desconectar--> DESCONECTANDO --> DESCONECTADO

    Encerramento cooperativo: parar() só liga um aviso (threading.Event), que o laço e
    as esperas conferem a cada volta. A thread nunca é morta no meio de uma leitura ou
    escrita.
    """

    # Espera máxima de cada leitura da porta: mesmo sem nada chegando, o laço volta a
    # atender a fila pelo menos nesse intervalo.
    TIMEOUT_LEITURA_S = 0.02
    TIMEOUT_ESCRITA_S = 0.5
    # Espera da fila quando não há porta aberta.
    ESPERA_FILA_S = 0.2
    # De quanto em quanto tempo a lista de portas do painel é atualizada.
    INTERVALO_PORTAS_S = 2.0
    # Abrir a porta reinicia o Uno: o bootloader leva perto de 2 s antes de o firmware
    # mandar o banner.
    TEMPO_BANNER_S = 4.0
    TEMPO_FIM_BANNER_S = 0.5
    # Depois do ACK: prazo do primeiro $DAT e coleta do zero da corrente (100 amostras
    # são 0,5 s a 200 Hz; em 9600 bps chegam só uns 43 pacotes por segundo).
    TEMPO_PRIMEIRA_TELEMETRIA_S = 2.0
    AMOSTRAS_CALIBRACAO = 100
    TEMPO_CALIBRACAO_S = 1.0
    # Telemetria: as leituras saem em lotes (uns 20 pacotes a 200 Hz), para a interface
    # não receber 200 sinais por segundo.
    INTERVALO_LOTE_S = 0.1
    # Watchdog: a placa manda 200 pacotes por segundo; 2 s sem nenhum válido é falha.
    TEMPO_SILENCIO_S = 2.0
    # Pacotes inválidos vão para o log resumidos, no máximo uma linha nesse intervalo.
    INTERVALO_AVISO_DESCARTE_S = 10.0
    # Média móvel da corrente: 10 amostras são 50 ms a 200 Hz.
    JANELA_MEDIA_CORRENTE = 10
    # Prazo para a placa confirmar o !0/!1 (ACK e STATUS_RELE no valor pedido).
    PRAZO_RELE_S = RastreadorRele.PRAZO_PADRAO_S

    _CONECTAR = "CONECTAR"
    _DESCONECTAR = "DESCONECTAR"
    _RELE = "RELE"

    estado_alterado = Signal(str, str)  # estado e detalhe para o painel
    portas_listadas = Signal(list)
    conectado = Signal(str, int, bool)  # porta, taxa e se foi uma reconexão automática
    desconectado = Signal(str)          # motivo
    falha_conexao = Signal(str)         # motivo
    conexao_perdida = Signal(str)       # motivo
    leituras_recebidas = Signal(list)   # lote de LeituraTelemetria
    rele_inicial = Signal(int)          # STATUS_RELE do primeiro pacote depois de conectar
    rele_confirmado = Signal(int)       # STATUS_RELE pedido, confirmado pela placa
    rele_nao_confirmado = Signal(int, str)  # STATUS_RELE pedido e motivo

    def __init__(self, abrir_porta=abrir_porta_serial, listar_portas=ConfiguracaoSerial.listar_portas):
        # Sem pai: o moveToThread não aceita um objeto que tem pai.
        super().__init__()
        self._abrir_porta = abrir_porta
        self._listar_portas = listar_portas

        self._fila = queue.Queue()
        self._parar = threading.Event()
        self._cancelar = threading.Event()

        self.estado = DESCONECTADO
        self._porta = None
        self._nome_porta = ""
        self._taxa = None
        self._timeout_resposta_s = ConfiguracaoSerial.TIMEOUT_PADRAO / 1000
        self._calibracao = Calibracao()

        self._leitor = LeitorLinhas()
        self._pendentes = deque()  # linhas já lidas da porta e ainda não tratadas

        self._lote = []
        self._inicio_lote = 0.0
        self._ultimo_pacote = 0.0
        self._media_corrente = MediaMovel(self.JANELA_MEDIA_CORRENTE)
        self._descartados = 0
        self.total_descartados = 0
        self._ultimo_descarte = ""
        self._proximo_aviso_descarte = 0.0

        self._rastreador = RastreadorRele(self.PRAZO_RELE_S)
        self._status_pedido = None  # STATUS_RELE do !0/!1 que aguarda confirmação

        self._portas = None
        self._proxima_listagem = 0.0

    # ------------------------------------------------------------------
    # Pedidos da interface (chamados na thread da interface)
    # ------------------------------------------------------------------

    def pedir_conexao(self, porta, taxa, timeout_ms):
        """Pede a conexão: a porta abre em 9600 e a placa é levada para a taxa escolhida."""
        self._fila.put((self._CONECTAR, porta, taxa, timeout_ms))

    def pedir_desconexao(self):
        """Pede a desconexão. Também interrompe um handshake em andamento."""
        self._cancelar.set()
        self._fila.put((self._DESCONECTAR,))

    def pedir_rele(self, status_rele):
        """Pede o !1 (status 1, relé ligado) ou o !0 (status 0, relé desligado).

        A resposta vem por rele_confirmado ou rele_nao_confirmado.
        """
        self._fila.put((self._RELE, status_rele))

    def parar(self):
        """Encerramento cooperativo: o laço termina na próxima volta."""
        self._parar.set()

    # ------------------------------------------------------------------
    # Laço da thread serial
    # ------------------------------------------------------------------

    @Slot()
    def executar(self):
        """Laço da thread serial. Ligado ao started da QThread, roda até parar()."""
        logger.info("SerialWorker iniciado na thread %d.", threading.get_ident())
        self._mudar_estado(DESCONECTADO)
        while not self._parar.is_set():
            if self.estado == DESCONECTADO:
                self._ciclo_desconectado()
            else:
                self._ciclo_conectado()
        self._finalizar()

    def _ciclo_desconectado(self):
        """Sem porta aberta: espera um pedido e mantém a lista de portas do painel em dia."""
        self._atualizar_portas()
        try:
            comando = self._fila.get(timeout=self.ESPERA_FILA_S)
        except queue.Empty:
            return
        self._atender(comando)

    def _ciclo_conectado(self):
        """Telemetria: atende a fila, lê os pacotes, entrega os lotes e vigia o silêncio."""
        try:
            self._atender_fila()
            if self.estado != CONECTADO:
                return
            self._ler_linhas()
        except (serial.SerialException, OSError) as erro:
            self._perder_conexao(f"erro na porta serial ({erro})")
            return

        agora = time.monotonic()
        while self._pendentes and self.estado == CONECTADO:
            self._tratar_linha(self._pendentes.popleft(), agora)
        if self.estado != CONECTADO:
            return

        if agora - self._inicio_lote >= self.INTERVALO_LOTE_S:
            self._emitir_lote()
        self._avisar_descartes(agora)
        if agora - self._ultimo_pacote >= self.TEMPO_SILENCIO_S:
            self._perder_conexao(f"nenhum pacote válido em {self.TEMPO_SILENCIO_S:.0f} s")

    def _atender_fila(self):
        """Atende, sem esperar, todos os pedidos que já estão na fila."""
        while True:
            try:
                comando = self._fila.get_nowait()
            except queue.Empty:
                return
            self._atender(comando)

    def _atender(self, comando):
        tipo = comando[0]
        if tipo == self._CONECTAR:
            self._conectar(*comando[1:])
        elif tipo == self._DESCONECTAR:
            self._cancelar.clear()
            if self.estado != DESCONECTADO:
                self._desconectar("encerrada pelo operador")
        elif tipo == self._RELE:
            self._comandar_rele(comando[1])

    def _interrompido(self) -> bool:
        return self._parar.is_set() or self._cancelar.is_set()

    def _mudar_estado(self, estado, detalhe=""):
        self.estado = estado
        self.estado_alterado.emit(estado, detalhe)

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------

    def _conectar(self, porta, taxa, timeout_ms):
        if self.estado != DESCONECTADO:
            logger.warning("Pedido de conexão ignorado: a conexão já está em %s.", self.estado)
            return
        if self._cancelar.is_set():
            # Um Desconectar que veio depois deste pedido já o cancelou.
            return

        self._nome_porta = porta
        self._taxa = taxa
        self._timeout_resposta_s = timeout_ms / 1000

        try:
            self._abrir()
            self._esperar_banner()
            self._pedir_taxa()
            self._confirmar_taxa()
            self._calibrar()
        except ConexaoInterrompidaError:
            self._fechar_porta()
            logger.info("Conexão com a placa em %s cancelada durante o handshake.", porta)
            self._mudar_estado(DESCONECTADO)
            self.desconectado.emit("cancelada pelo operador durante o handshake")
        except (FalhaConexaoError, serial.SerialException, OSError) as erro:
            self._fechar_porta()
            logger.error("Falha ao conectar na placa em %s: %s.", porta, erro)
            self._mudar_estado(DESCONECTADO)
            self.falha_conexao.emit(str(erro))
        else:
            self._iniciar_telemetria()
            self._mudar_estado(CONECTADO, f"{porta} @ {taxa} bps")
            logger.info("Conectado à placa em %s a %d bps: telemetria liberada.", porta, taxa)
            self.conectado.emit(porta, taxa, False)

    def _abrir(self):
        """Abre a porta em 9600 bps, a taxa em que a placa liga."""
        self._mudar_estado(CONECTANDO, f"{self._nome_porta} em {TAXA_INICIAL} bps, aguardando a placa")
        self._leitor.limpar()
        self._pendentes.clear()
        try:
            self._porta = self._abrir_porta(self._nome_porta)
        except (serial.SerialException, OSError, ValueError) as erro:
            raise FalhaConexaoError(self._explicar_erro_abertura(erro)) from erro
        logger.info("Porta %s aberta em %d bps.", self._nome_porta, TAXA_INICIAL)

    def _esperar_banner(self):
        """Espera o banner que o Uno manda ao reiniciar (abrir a porta reinicia a placa).

        Enquanto o bootloader roda, um comando enviado se perde: o !S só vai depois do
        banner. Se o banner não vier (placa que não reinicia ao abrir a porta ou que já
        estava em espera), o handshake segue assim mesmo, porque a placa em espera
        aceita o !S do mesmo jeito; se ela não responder, a falha aparece no ACK.
        """
        banner = self._esperar_linha(lambda linha: linha.tipo == LinhaSerial.BANNER, self.TEMPO_BANNER_S)
        if banner is None:
            logger.warning(
                "Banner da placa não chegou em %.1f s em %s; o comando de taxa vai ser enviado assim mesmo.",
                self.TEMPO_BANNER_S, self._nome_porta,
            )
            return

        logger.info("Placa em espera em %s: '%s'.", self._nome_porta, banner.texto)
        # O banner termina numa linha de "=": o !S vai depois dela.
        self._esperar_linha(lambda linha: linha.texto.startswith("="), self.TEMPO_FIM_BANNER_S)

    def _pedir_taxa(self):
        """Primeiro pacote do handshake: !S<taxa>, ainda em 9600 bps."""
        try:
            comando = montar_comando_taxa(self._taxa)
        except ProtocoloError as erro:
            raise FalhaConexaoError(str(erro)) from erro

        self._mudar_estado(NEGOCIANDO, f"{comando.strip()} enviado, aguardando o ACK em {TAXA_INICIAL} bps")
        self._escrever(comando)
        logger.info("Handshake: %s enviado à placa em %d bps.", comando.strip(), TAXA_INICIAL)

    def _confirmar_taxa(self):
        """Lê a resposta do !S ainda em 9600 e passa a porta para a taxa nova.

        A placa responde ACK (ou ERR) na taxa antiga e só depois troca a dela. A porta
        troca de taxa aberta: fechar e abrir de novo mexeria no DTR, o Uno reiniciaria e
        voltaria ao modo de espera em 9600, desfazendo o handshake.
        """
        resposta = self._esperar_linha(
            lambda linha: linha.tipo in (LinhaSerial.ACK_TAXA, LinhaSerial.ERR_TAXA),
            self._timeout_resposta_s,
        )
        if resposta is None:
            raise FalhaConexaoError(
                f"a placa não respondeu ao !S{self._taxa} em {self._timeout_resposta_s * 1000:.0f} ms "
                "(confira se a porta é a do Arduino e se ele está com o firmware do professor)"
            )
        if resposta.tipo == LinhaSerial.ERR_TAXA:
            raise FalhaConexaoError(f"a placa recusou a taxa {self._taxa}: '{resposta.texto}'")
        if resposta.valor != self._taxa:
            raise FalhaConexaoError(f"a placa confirmou {resposta.valor} bps em vez de {self._taxa}")

        logger.info("Handshake: placa respondeu '%s' em %d bps.", resposta.texto, TAXA_INICIAL)
        self._porta.baudrate = self._taxa
        # O que chegou depois do ACK foi enviado durante a troca de taxa: é lixo.
        self._porta.reset_input_buffer()
        self._leitor.limpar()
        self._pendentes.clear()

    def _calibrar(self):
        """Mede o zero da corrente nas primeiras leituras, com o relé desligado.

        O firmware começa com o relé desligado: sem carga, a média de A1 é o zero do
        ACS712 (perto de 512). Com o relé ligado há corrente passando, e o zero do
        config.json é mantido. As leituras da calibração não vão para a tela nem para
        o banco.
        """
        self._calibracao = Calibracao.do_config()
        self._mudar_estado(CALIBRANDO, f"{self._nome_porta} @ {self._taxa} bps")

        def eh_dados(linha):
            return linha.tipo == LinhaSerial.DADOS

        primeira = self._esperar_linha(eh_dados, self.TEMPO_PRIMEIRA_TELEMETRIA_S)
        if primeira is None:
            raise FalhaConexaoError(
                f"a placa confirmou {self._taxa} bps, mas a telemetria não chegou em "
                f"{self.TEMPO_PRIMEIRA_TELEMETRIA_S:.0f} s"
            )

        amostras = [primeira.valor]
        limite = time.monotonic() + self.TEMPO_CALIBRACAO_S
        while len(amostras) < self.AMOSTRAS_CALIBRACAO and time.monotonic() < limite:
            linha = self._esperar_linha(eh_dados, limite - time.monotonic())
            if linha is None:
                break
            amostras.append(linha.valor)

        zero_configurado = self._calibracao.zero_corrente_adc
        if not ConfigManager.get("calibrar_zero_corrente", True):
            logger.info("Calibração do zero desligada no config.json: zero da corrente fixo em %.1f.", zero_configurado)
            return
        if any(campos["status_rele"] == 1 for campos in amostras):
            logger.warning(
                "Relé ligado durante a calibração: há carga no sensor. Mantido o zero de %.1f do config.json.",
                zero_configurado,
            )
            return

        zero = self._calibracao.calibrar_zero(campos["a1"] for campos in amostras)
        if abs(zero - Calibracao.ZERO_CORRENTE_PADRAO) > Calibracao.DESVIO_MAXIMO_ZERO:
            # A Calibracao já avisou no log: um zero tão longe do meio da escala não é usado.
            self._calibracao.zero_corrente_adc = zero_configurado
            logger.warning("Zero calibrado descartado; mantido o zero de %.1f do config.json.", zero_configurado)

    @staticmethod
    def _explicar_erro_abertura(erro) -> str:
        texto = str(erro)
        if "PermissionError" in texto or "Acesso negado" in texto or "Access is denied" in texto:
            return f"a porta está em uso por outro programa (feche o Monitor Serial da Arduino IDE) - {texto}"
        if "FileNotFoundError" in texto:
            return f"a porta não existe ou a placa foi desconectada - {texto}"
        return f"não foi possível abrir a porta - {texto}"

    # ------------------------------------------------------------------
    # Telemetria
    # ------------------------------------------------------------------

    def _iniciar_telemetria(self):
        agora = time.monotonic()
        self._lote = []
        self._inicio_lote = agora
        self._ultimo_pacote = agora
        self._media_corrente.limpar()
        self._descartados = 0
        self._proximo_aviso_descarte = agora + self.INTERVALO_AVISO_DESCARTE_S
        self._rastreador.prazo_s = self.PRAZO_RELE_S
        self._rastreador.reiniciar()
        self._status_pedido = None

    def _tratar_linha(self, texto, agora):
        try:
            linha = interpretar_linha(texto)
        except ProtocoloError as erro:
            # Checksum errado, campo faltando ou valor fora da faixa: o pacote é descartado.
            self._contar_descarte(str(erro))
            return

        if linha.tipo == LinhaSerial.DADOS:
            self._receber_dados(linha.valor, agora)
        elif linha.tipo in (LinhaSerial.ACK_RELE_LIGADO, LinhaSerial.ACK_RELE_DESLIGADO, LinhaSerial.ACK_RELE_ALTERNADO):
            logger.info("Placa em %s respondeu: '%s'.", self._nome_porta, linha.texto)
            self._rastreador.ack_recebido(linha.tipo)
        elif linha.tipo in (LinhaSerial.BANNER, LinhaSerial.ACK_PAUSA):
            # A placa voltou sozinha ao modo de espera (botão de reset, queda de alimentação).
            self._perder_conexao(f"a placa voltou ao modo de espera ('{linha.texto}')")
        elif linha.tipo == LinhaSerial.DESCONHECIDA:
            self._contar_descarte(f"linha fora do protocolo: {texto!r}")
        elif linha.tipo not in (LinhaSerial.VAZIA, LinhaSerial.INFORMATIVA):
            logger.info("Placa em %s respondeu: '%s'.", self._nome_porta, linha.texto)

    def _receber_dados(self, campos, agora):
        """Converte um $DAT válido em LeituraTelemetria e o guarda no lote."""
        self._ultimo_pacote = agora
        leitura = LeituraTelemetria.de_pacote(campos, self._calibracao)
        # Média móvel só na corrente: uma contagem do ADC vale uns 74 mA, e o ruído do
        # ACS712 faria o mostrador e o alarme tremerem.
        leitura.corrente_a = self._media_corrente.adicionar(leitura.corrente_a)
        self._lote.append(leitura)
        self._acompanhar_rele(leitura.status_rele, agora)

    # ------------------------------------------------------------------
    # Relé: !0/!1 confirmados por ACK e STATUS_RELE
    # ------------------------------------------------------------------

    def _comandar_rele(self, status_rele):
        """Envia o !1 ou o !0. A confirmação vem depois, pela telemetria (RastreadorRele).

        O ACK sozinho não basta: o comando só é confirmado quando o STATUS_RELE dos
        pacotes, que o firmware lê do próprio pino de saída, chega no valor pedido.
        """
        if status_rele not in (0, 1):
            self.rele_nao_confirmado.emit(status_rele, "STATUS_RELE pedido diferente de 0 e 1")
            return
        if self.estado != CONECTADO:
            self.rele_nao_confirmado.emit(status_rele, "a placa não está conectada")
            return
        if self._rastreador.tem_comando_pendente:
            self.rele_nao_confirmado.emit(status_rele, "a placa ainda não confirmou o comando anterior")
            return

        comando = COMANDO_RELE_LIGA if status_rele == 1 else COMANDO_RELE_DESLIGA
        # Guardado antes de escrever: se a escrita falhar (cabo puxado), a perda da
        # conexão recusa este pedido.
        self._status_pedido = status_rele
        self._escrever(comando)
        self._rastreador.comando_enviado(comando, time.monotonic())
        logger.info("Comando %s enviado à placa; aguardando o ACK e o STATUS_RELE.", comando.strip())

    def _acompanhar_rele(self, status_rele, agora):
        resultado = self._rastreador.atualizar(status_rele, agora)
        if resultado == RastreadorRele.INICIAL:
            logger.info("Relé da placa ao conectar: STATUS_RELE = %d.", status_rele)
            self.rele_inicial.emit(status_rele)
        elif resultado == RastreadorRele.CONFIRMADO:
            self._status_pedido = None
            logger.info("Placa confirmou o relé: ACK recebido e STATUS_RELE = %d.", status_rele)
            self.rele_confirmado.emit(status_rele)
        elif resultado == RastreadorRele.EXPIRADO:
            pedido, self._status_pedido = self._status_pedido, None
            motivo = (
                f"sem ACK e STATUS_RELE = {pedido} em {self.PRAZO_RELE_S:.0f} s "
                f"(STATUS_RELE ficou em {status_rele})"
            )
            logger.warning("A placa não confirmou o comando do relé: %s.", motivo)
            self.rele_nao_confirmado.emit(pedido, motivo)
        elif resultado == RastreadorRele.ESPONTANEO:
            logger.warning("STATUS_RELE mudou para %d sem comando do operador.", status_rele)

    def _recusar_pendente(self, motivo):
        """Avisa que o !0/!1 que aguardava confirmação não vai mais ser confirmado."""
        if self._status_pedido is None:
            return
        pedido, self._status_pedido = self._status_pedido, None
        logger.warning("Comando do relé sem confirmação: %s.", motivo)
        self.rele_nao_confirmado.emit(pedido, motivo)

    def _emitir_lote(self):
        """Entrega à interface (e, por ela, ao banco) as leituras juntadas desde o último lote."""
        if self._lote:
            lote, self._lote = self._lote, []
            self.leituras_recebidas.emit(lote)
        self._inicio_lote = time.monotonic()

    def _contar_descarte(self, motivo):
        self._descartados += 1
        self.total_descartados += 1
        self._ultimo_descarte = motivo

    def _avisar_descartes(self, agora):
        """Resume os descartados no log: a 200 pacotes por segundo, uma linha por pacote inundaria o arquivo."""
        if agora < self._proximo_aviso_descarte:
            return
        self._proximo_aviso_descarte = agora + self.INTERVALO_AVISO_DESCARTE_S
        if self._descartados:
            logger.warning(
                "%d pacote(s) inválido(s) da placa descartado(s) nos últimos %.0f s. Último: %s",
                self._descartados, self.INTERVALO_AVISO_DESCARTE_S, self._ultimo_descarte,
            )
            self._descartados = 0

    def _perder_conexao(self, motivo):
        """A placa parou de responder: cabo puxado, placa reiniciada ou travada."""
        logger.warning("Conexão com a placa em %s perdida: %s.", self._nome_porta, motivo)
        self._emitir_lote()
        self._fechar_porta()
        self._recusar_pendente("a conexão com a placa caiu antes da confirmação")
        self._mudar_estado(DESCONECTADO)
        self.conexao_perdida.emit(motivo)

    # ------------------------------------------------------------------
    # Leitura e escrita na porta
    # ------------------------------------------------------------------

    def _ler_linhas(self):
        """Lê o que chegou na porta (espera até TIMEOUT_LEITURA_S) e guarda as linhas completas."""
        dados = self._porta.read(self._porta.in_waiting or 1)
        if dados:
            self._pendentes.extend(self._leitor.adicionar(dados))

    def _esperar_linha(self, aceitar, prazo_s, interrompivel=True):
        """Lê até chegar uma linha que aceitar(linha) aprove e devolve essa LinhaSerial.

        As outras linhas são descartadas, inclusive $DAT com checksum errado. Devolve
        None se o prazo acabar. Se interrompivel, lança ConexaoInterrompidaError quando o
        operador desconecta ou a aplicação fecha durante a espera; a espera do ACK do !P
        não é interrompível, porque ela já faz parte da desconexão.
        """
        limite = time.monotonic() + prazo_s
        while True:
            while self._pendentes:
                texto = self._pendentes.popleft()
                try:
                    linha = interpretar_linha(texto)
                except ProtocoloError:
                    continue
                if aceitar(linha):
                    return linha
            if interrompivel and self._interrompido():
                raise ConexaoInterrompidaError()
            if time.monotonic() >= limite:
                return None
            self._ler_linhas()

    def _escrever(self, comando):
        self._porta.write(comando.encode("ascii"))

    # ------------------------------------------------------------------
    # Desconexão
    # ------------------------------------------------------------------

    def _desconectar(self, motivo):
        """Pausa a placa (!P), que volta a 9600 e fica em espera, e fecha a porta."""
        self._mudar_estado(DESCONECTANDO, self._nome_porta)
        self._emitir_lote()
        self._recusar_pendente("a conexão foi encerrada antes da confirmação")
        if self._porta is not None:
            self._pausar_placa()
        self._fechar_porta()
        logger.info("Conexão com a placa em %s %s.", self._nome_porta, motivo)
        self._mudar_estado(DESCONECTADO)
        self.desconectado.emit(motivo)

    def _pausar_placa(self):
        """Envia o !P e espera o ACK. Uma falha aqui só vai para o log: a porta fecha de qualquer jeito."""
        try:
            self._escrever(COMANDO_PAUSA)
            ack = self._esperar_linha(
                lambda linha: linha.tipo == LinhaSerial.ACK_PAUSA, self._timeout_resposta_s, interrompivel=False
            )
        except (serial.SerialException, OSError) as erro:
            logger.warning("Não foi possível pausar a placa em %s: %s.", self._nome_porta, erro)
            return
        if ack is None:
            logger.warning(
                "A placa em %s não confirmou o !P em %.0f ms.", self._nome_porta, self._timeout_resposta_s * 1000
            )
        else:
            logger.info("Placa pausada: '%s'.", ack.texto)

    def _fechar_porta(self):
        if self._porta is None:
            return
        try:
            self._porta.close()
        except (serial.SerialException, OSError) as erro:
            # Com o cabo puxado o close também pode falhar; a porta é abandonada assim mesmo.
            logger.warning("Falha ao fechar a porta %s: %s", self._nome_porta, erro)
        self._porta = None

    def _atualizar_portas(self):
        agora = time.monotonic()
        if agora < self._proxima_listagem:
            return
        self._proxima_listagem = agora + self.INTERVALO_PORTAS_S
        try:
            portas = self._listar_portas()
        except OSError as erro:
            logger.warning("Não foi possível listar as portas seriais: %s", erro)
            return
        if portas != self._portas:
            self._portas = portas
            self.portas_listadas.emit(list(portas))

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    def _finalizar(self):
        self._fechar_porta()
        self.estado = DESCONECTADO
        logger.info("SerialWorker encerrado na thread %d.", threading.get_ident())
        # O laço rodou dentro do started da QThread. O quit() faz o exec() que vem
        # depois dele terminar na hora, e a thread acaba.
        self.thread().quit()
