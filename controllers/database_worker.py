import logging
import math
import sqlite3
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from database.connection import Database
from models.agregador_leituras import AgregadorLeituras
from models.dispositivo import Dispositivo
from models.dispositivo_repository import DispositivoRepository
from models.evento_historico import EventoHistorico
from models.evento_repository import EventoRepository
from models.filtro_historico import FiltroHistorico
from models.leitura_repository import LeituraRepository

logger = logging.getLogger("smartgrid")


class FalhaOperacaoError(RuntimeError):
    """Interrompe a gravação do corte ou do religamento no meio da transação. Como é
    lançada dentro do with conn:, o SQLite desfaz tudo o que já tinha sido feito (ROLLBACK)."""


class DatabaseWorker(QObject):
    """Acesso ao banco fora da thread da interface.

    O BancoController move o worker para uma QThread (moveToThread). A partir daí os
    slots dele rodam na thread do banco, um de cada vez, na ordem em que os pedidos
    chegam pela fila de eventos dessa thread. A interface nunca chama estes métodos
    diretamente, porque eles rodariam na thread dela: ela emite os sinais do
    BancoController, ligados a estes slots.

    A conexão SQLite é aberta e fechada dentro da thread do banco, porque o sqlite3 não
    deixa usar uma conexão em outra thread.

    Banco ocupado (database is locked): a conexão já espera até 5 s pelo bloqueio de
    outra conexão. Se ainda assim ele não liberar, leituras e eventos ficam guardados e
    um timer desta thread tenta de novo a cada INTERVALO_NOVA_TENTATIVA_MS. Enquanto o
    banco está ocupado, o que chega só entra na fila: tentar a cada lote faria o worker
    esperar os 5 s de novo a cada lote.
    """

    # O relé recebe o comando e o disjuntor sinaliza a proteção: os dois mudam juntos.
    TAGS_OPERACAO_RELE = (Dispositivo.TAG_RELE_EMERGENCIA, Dispositivo.TAG_DISJUNTOR_PRINCIPAL)

    INTERVALO_NOVA_TENTATIVA_MS = 2000
    # Teto das leituras guardadas com o banco ocupado: 10 minutos de janelas de 500 ms.
    MAXIMO_JANELAS_PENDENTES = 1200
    MOTIVO_BANCO_OCUPADO = "o banco está ocupado por outra conexão (database is locked)"

    falhou = Signal(str)

    # Respostas dos pedidos de evento, entregues na thread da interface pela fila dela.
    evento_gravado = Signal(object)
    evento_nao_gravado = Signal(object, str)

    # Respostas da gravação do corte ou do religamento: status gravado e eventos, ou
    # status pedido, motivo da falha e status do disjuntor relido depois do ROLLBACK.
    operacao_rele_gravada = Signal(str, list)
    operacao_rele_falhou = Signal(str, str, str)

    # Respostas da consulta de histórico: número do pedido, leituras e quantas janelas
    # gravadas formam cada ponto (1 = sem agrupamento); ou número do pedido e motivo.
    historico_consultado = Signal(int, list, int)
    historico_falhou = Signal(int, str)

    def __init__(self):
        # Sem pai: o moveToThread não aceita um objeto que tem pai.
        super().__init__()
        self._conn = None
        self._agregador = AgregadorLeituras.do_config()
        self._avisou_sem_conexao = False

        self._janelas_pendentes = []
        self._eventos_pendentes = []
        self._banco_ocupado = False
        self._avisou_descarte = False
        self._timer_pendencias = None

    @staticmethod
    def _eh_banco_ocupado(erro) -> bool:
        """database is locked: outra conexão segurou o banco além do timeout da conexão."""
        return isinstance(erro, sqlite3.OperationalError) and "locked" in str(erro).lower()

    @Slot()
    def abrir(self):
        """Abre a conexão do worker. Ligado ao started da QThread, roda na thread do banco."""
        # Criado aqui, e não no __init__, para o timer pertencer à thread do banco.
        self._timer_pendencias = QTimer(self)
        self._timer_pendencias.setInterval(self.INTERVALO_NOVA_TENTATIVA_MS)
        self._timer_pendencias.timeout.connect(self._tentar_pendencias)

        try:
            self._conn = Database.get_connection()
        except sqlite3.Error as erro:
            logger.error("DatabaseWorker: falha ao abrir a conexão com o banco: %s", erro)
            self.falhou.emit(str(erro))
            return

        logger.info(
            "DatabaseWorker iniciado: conexão aberta na thread %d, leituras gravadas em janelas de %d ms.",
            threading.get_ident(), self._agregador.taxa_ms,
        )

    # ------------------------------------------------------------------
    # Leituras
    # ------------------------------------------------------------------

    @Slot(list)
    def gravar_leituras(self, leituras):
        """Recebe um lote de LeituraTelemetria e grava a média de cada janela que fechou.

        As janelas fechadas pelo lote inteiro vão para o banco numa única transação, com
        um único executemany: a 200 leituras por segundo, gravar uma a uma seria lento.
        """
        janelas = []
        for leitura in leituras:
            janelas.extend(self._agregador.adicionar(leitura))
        if not janelas:
            return

        self._janelas_pendentes.extend(janelas)
        self._limitar_janelas_pendentes()
        if not self._banco_ocupado:
            self._gravar_janelas_pendentes()

    def _gravar_janelas_pendentes(self) -> bool:
        """Grava as janelas guardadas. Devolve False se o banco continuar ocupado."""
        if not self._janelas_pendentes:
            return True

        if self._conn is None:
            # Avisa uma vez só: chegam duas janelas por segundo e o log ficaria inundado.
            if not self._avisou_sem_conexao:
                logger.error("Leituras descartadas: a conexão do DatabaseWorker não está aberta.")
                self._avisou_sem_conexao = True
            self._janelas_pendentes = []
            return True

        janelas = self._janelas_pendentes
        try:
            with self._conn:
                LeituraRepository.inserir_lote(janelas, conn=self._conn)
        except sqlite3.IntegrityError as erro:
            self._janelas_pendentes = []
            self._gravar_janelas_uma_a_uma(janelas, erro)
            return not self._banco_ocupado
        except sqlite3.Error as erro:
            if self._eh_banco_ocupado(erro):
                self._marcar_banco_ocupado()
                return False
            logger.error("Falha ao gravar %d janela(s) de leituras. Rollback executado: %s.", len(janelas), erro)
            self._janelas_pendentes = []
            return True

        self._janelas_pendentes = []
        return True

    def _gravar_janelas_uma_a_uma(self, janelas, erro_do_lote):
        """O CHECK recusou uma janela e a transação do lote inteiro foi desfeita.

        Regrava uma a uma, cada uma na própria transação, para salvar as válidas e
        descartar só as que o banco recusa.
        """
        gravadas = descartadas = 0
        for indice, janela in enumerate(janelas):
            try:
                with self._conn:
                    LeituraRepository.inserir_lote([janela], conn=self._conn)
            except sqlite3.IntegrityError as erro:
                descartadas += 1
                logger.warning("Janela de leituras de %s descartada pelo banco: %s.", janela.get_data_hora(), erro)
                continue
            except sqlite3.Error as erro:
                if self._eh_banco_ocupado(erro):
                    # O resto volta para a fila e é tentado quando o banco liberar.
                    self._janelas_pendentes = janelas[indice:] + self._janelas_pendentes
                    self._marcar_banco_ocupado()
                    break
                descartadas += 1
                logger.error("Janela de leituras de %s não gravada: %s.", janela.get_data_hora(), erro)
                continue
            gravadas += 1

        logger.error(
            "Lote de leituras recusado pelo banco (%s). Rollback executado; regravado janela a janela: "
            "%d gravada(s) e %d descartada(s).",
            erro_do_lote, gravadas, descartadas,
        )

    def _limitar_janelas_pendentes(self):
        excesso = len(self._janelas_pendentes) - self.MAXIMO_JANELAS_PENDENTES
        if excesso <= 0:
            return
        del self._janelas_pendentes[:excesso]
        if not self._avisou_descarte:
            logger.error(
                "Banco ocupado por muito tempo: as leituras guardadas passaram de %d janelas, "
                "e as mais antigas estão sendo descartadas.",
                self.MAXIMO_JANELAS_PENDENTES,
            )
            self._avisou_descarte = True

    # ------------------------------------------------------------------
    # Consulta de histórico
    # ------------------------------------------------------------------

    @Slot(int, object)
    def consultar_historico(self, pedido, filtro):
        """Consulta as leituras do FiltroHistorico e devolve por historico_consultado.

        Roda na thread do banco: a tela continua respondendo enquanto a consulta anda.
        Se o filtro tiver mais leituras que FiltroHistorico.QUANTIDADE_MAXIMA (um intervalo
        longo: 2 leituras por segundo dão 7.200 por hora), elas são agrupadas em blocos
        seguidos e cada ponto devolvido é a média de um bloco.
        """
        try:
            filtro.validar()
        except ValueError as erro:
            logger.warning("Consulta de histórico recusada: %s", erro)
            self.historico_falhou.emit(pedido, str(erro))
            return

        if self._conn is None:
            logger.error("Consulta de histórico não feita: a conexão do DatabaseWorker não está aberta.")
            self.historico_falhou.emit(pedido, "a conexão com o banco não está aberta")
            return

        inicio = time.perf_counter()
        try:
            total = LeituraRepository.contar(filtro, conn=self._conn)
            agrupar = max(1, math.ceil(total / FiltroHistorico.QUANTIDADE_MAXIMA))
            leituras = LeituraRepository.listar(filtro, conn=self._conn, agrupar=agrupar)
        except sqlite3.Error as erro:
            motivo = self.MOTIVO_BANCO_OCUPADO if self._eh_banco_ocupado(erro) else str(erro)
            logger.error("Falha na consulta de histórico (%s): %s", filtro.descrever(), motivo)
            self.historico_falhou.emit(pedido, motivo)
            return

        duracao_ms = (time.perf_counter() - inicio) * 1000
        if agrupar > 1:
            logger.info(
                "Histórico consultado (%s): %d leituras agrupadas em %d pontos de %d em %.0f ms.",
                filtro.descrever(), total, len(leituras), agrupar, duracao_ms,
            )
        else:
            logger.info(
                "Histórico consultado (%s): %d leitura(s) em %.0f ms.", filtro.descrever(), len(leituras), duracao_ms
            )
        self.historico_consultado.emit(pedido, leituras, agrupar)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    @Slot(object)
    def registrar_evento(self, evento):
        """Grava um EventoHistorico e avisa a interface com evento_gravado.

        A tabela do dashboard só ganha a linha quando esse sinal chega: ela mostra apenas
        o que está gravado no banco. Se o banco recusar o evento, ele volta pelo
        evento_nao_gravado com o motivo; se o banco estiver ocupado, ele fica guardado e é
        gravado (e só então aparece na tabela) quando o banco liberar.
        """
        if self._conn is None:
            logger.error("Evento '%s' não gravado: a conexão do DatabaseWorker não está aberta.", evento.tipo)
            self.evento_nao_gravado.emit(evento, "a conexão com o banco não está aberta")
            return

        self._eventos_pendentes.append(evento)
        if not self._banco_ocupado:
            self._gravar_eventos_pendentes()

    def _gravar_eventos_pendentes(self) -> bool:
        """Grava os eventos guardados, na ordem em que chegaram. Devolve False se o banco
        continuar ocupado (o evento da vez e os seguintes continuam guardados)."""
        while self._eventos_pendentes:
            evento = self._eventos_pendentes[0]
            try:
                with self._conn:
                    EventoRepository.inserir(evento, conn=self._conn)
            except sqlite3.IntegrityError as erro:
                # Dado inválido: tentar de novo daria o mesmo erro.
                self._eventos_pendentes.pop(0)
                logger.error("Evento '%s' recusado pelo banco. Rollback executado: %s.", evento.tipo, erro)
                self.evento_nao_gravado.emit(evento, f"dado recusado pelo banco: {erro}")
                continue
            except sqlite3.Error as erro:
                if self._eh_banco_ocupado(erro):
                    self._marcar_banco_ocupado()
                    return False
                self._eventos_pendentes.pop(0)
                logger.error("Falha ao gravar o evento '%s' no histórico. Rollback executado: %s.", evento.tipo, erro)
                self.evento_nao_gravado.emit(evento, str(erro))
                continue

            self._eventos_pendentes.pop(0)
            self.evento_gravado.emit(evento)
        return True

    @Slot(int, object)
    def registrar_rele_espontaneo(self, status_rele, momento):
        """Relé que mudou sem comando do operador (RastreadorRele.ESPONTANEO).

        É uma anomalia de hardware: vai para o log como WARNING e para o histórico. O
        momento é o da detecção, não o da gravação, que pode vir alguns milissegundos depois.
        """
        logger.warning("Relé de emergência mudou sem comando do operador: STATUS_RELE = %d.", status_rele)
        self.registrar_evento(EventoHistorico.rele_espontaneo(status_rele, momento))

    @Slot(object)
    def registrar_botao_local(self, momento):
        """Aperto confirmado do botão da bancada (DetectorBotao), o disparo local do disjuntor."""
        logger.warning("Botão local da bancada pressionado: disparo do disjuntor solicitado.")
        self.registrar_evento(EventoHistorico.botao_local(momento))

    # ------------------------------------------------------------------
    # Corte e religamento
    # ------------------------------------------------------------------

    @Slot(str, list, bool)
    def gravar_operacao_rele(self, status, eventos, simular_falha):
        """Grava o corte (ABERTO) ou o religamento (FECHADO) numa única transação: o status
        do relé e do disjuntor e os eventos do histórico.

        Só é pedida depois que a placa confirmou o comando. O with conn: faz o COMMIT só
        se o bloco inteiro terminar sem erro; qualquer exceção no meio, inclusive a falha
        simulada, faz o SQLite desfazer tudo (ROLLBACK): o status nunca muda sem o
        evento, nem o evento fica gravado sem o status. Com o banco ocupado a operação não
        fica guardada: o operador recebe a falha na hora e decide se tenta de novo.
        """
        if self._conn is None:
            self.operacao_rele_falhou.emit(status, "a conexão com o banco não está aberta", "não foi possível consultar")
            return

        try:
            with self._conn:
                for tag in self.TAGS_OPERACAO_RELE:
                    if not DispositivoRepository.atualizar_status(tag, status, conn=self._conn):
                        raise FalhaOperacaoError(f"dispositivo {tag} não está cadastrado no banco")

                if simular_falha:
                    raise FalhaOperacaoError(
                        "falha simulada entre a atualização do disjuntor e o registro do evento"
                    )

                for evento in eventos:
                    EventoRepository.inserir(evento, conn=self._conn)
        except (FalhaOperacaoError, sqlite3.Error) as erro:
            motivo = self.MOTIVO_BANCO_OCUPADO if self._eh_banco_ocupado(erro) else str(erro)
            self.operacao_rele_falhou.emit(status, motivo, self._status_disjuntor_no_banco())
            return

        self.operacao_rele_gravada.emit(status, eventos)

    @staticmethod
    def _status_disjuntor_no_banco() -> str:
        """Relê o status do disjuntor depois do ROLLBACK, para comprovar que ficou o anterior."""
        try:
            dispositivo = DispositivoRepository.buscar_por_tag(Dispositivo.TAG_DISJUNTOR_PRINCIPAL)
        except sqlite3.Error as erro:
            logger.error("Não foi possível reler o estado do disjuntor após o rollback: %s", erro)
            return "não foi possível consultar"

        if dispositivo is None:
            return "não cadastrado"
        return dispositivo.status

    # ------------------------------------------------------------------
    # Banco ocupado: guardar e tentar de novo
    # ------------------------------------------------------------------

    def _marcar_banco_ocupado(self):
        if self._banco_ocupado:
            return
        self._banco_ocupado = True
        logger.warning(
            "Banco ocupado por outra conexão (database is locked): leituras e eventos ficam guardados "
            "e são gravados quando ele liberar."
        )
        self.falhou.emit("Banco ocupado por outra conexão: leituras e eventos serão gravados quando ele liberar.")
        self._timer_pendencias.start()

    @Slot()
    def _tentar_pendencias(self):
        """Ligado ao timer: tenta gravar o que ficou guardado enquanto o banco estava ocupado."""
        if not (self._gravar_eventos_pendentes() and self._gravar_janelas_pendentes()):
            return

        self._timer_pendencias.stop()
        self._banco_ocupado = False
        self._avisou_descarte = False
        logger.info("Banco liberado: as leituras e os eventos guardados foram gravados.")

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    @Slot()
    def encerrar(self):
        """Grava o que estiver guardado, fecha a conexão e termina o laço de eventos da thread.

        O pedido chega pela fila depois dos que já estavam nela: os lotes pendentes são
        gravados antes, e nada é interrompido no meio de uma transação.
        """
        if self._timer_pendencias is not None:
            self._timer_pendencias.stop()
        self._janelas_pendentes.extend(self._agregador.finalizar())

        if self._conn is not None:
            # Última tentativa, mesmo com o banco ocupado: ele pode ter acabado de liberar.
            # Se os eventos ainda esbarrarem no bloqueio, as leituras nem são tentadas, porque
            # cada tentativa pode esperar o timeout da conexão e a interface espera um tempo
            # limitado (BancoController.TEMPO_MAXIMO_ENCERRAMENTO_MS).
            if self._gravar_eventos_pendentes():
                self._gravar_janelas_pendentes()

        if self._eventos_pendentes or self._janelas_pendentes:
            logger.error(
                "Encerramento com o banco ocupado: %d evento(s) e %d janela(s) de leituras não foram gravados.",
                len(self._eventos_pendentes), len(self._janelas_pendentes),
            )

        if self._conn is not None:
            self._conn.close()
            self._conn = None

        logger.info("DatabaseWorker encerrado: conexão fechada na thread %d.", threading.get_ident())
        # O quit() pode ser chamado de dentro da própria thread: o laço de eventos dela
        # termina assim que este slot voltar.
        self.thread().quit()
