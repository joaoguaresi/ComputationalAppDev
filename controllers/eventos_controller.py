import logging
import sqlite3

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHeaderView, QMessageBox, QTableWidgetItem

from models.evento_repository import EventoRepository

logger = logging.getLogger("smartgrid")


class EventosController(QObject):
    """Histórico de eventos: liga a QTableWidget do dashboard à tabela eventos do banco.

    A tabela da tela não guarda dados próprios. Ela é preenchida pelo banco na
    inicialização (EventoRepository.listar_todos) e cada evento novo só aparece nela
    depois de gravado no SQLite, pelo sinal evento_registrado.
    """

    LARGURA_DATA_HORA = 150
    LARGURA_TIPO = 180
    DURACAO_AVISO_MS = 10000

    # Emitido depois que o evento foi gravado no banco.
    evento_registrado = Signal(object)

    def __init__(self, janela, tabela):
        super().__init__(janela)
        self.janela = janela
        self.tabela = tabela

        self._configurar_colunas()
        self.evento_registrado.connect(self._adicionar_linha)

        self.carregar_historico()

    def _configurar_colunas(self):
        """Data/Hora e Tipo com largura fixa, Valor Medido na largura do conteúdo e a
        Descrição com todo o espaço que sobra.

        A descrição que ainda assim não cabe quebra em mais de uma linha, em vez de ser
        cortada com "...". Como a altura necessária depende da largura da coluna, as
        linhas são reajustadas sempre que uma coluna muda de largura (por exemplo, quando
        a janela abre ou é redimensionada).
        """
        cabecalho = self.tabela.horizontalHeader()
        self.tabela.setColumnWidth(0, self.LARGURA_DATA_HORA)
        self.tabela.setColumnWidth(1, self.LARGURA_TIPO)
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(2, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabela.setWordWrap(True)

        # O reajuste roda logo depois do layout, num timer de disparo único: durante o
        # sinal sectionResized a coluna ainda não tem a largura nova, e vários
        # redimensionamentos seguidos viram um único recálculo.
        self._ajuste_das_linhas = QTimer(self)
        self._ajuste_das_linhas.setSingleShot(True)
        self._ajuste_das_linhas.setInterval(0)
        self._ajuste_das_linhas.timeout.connect(self.tabela.resizeRowsToContents)
        cabecalho.sectionResized.connect(self._agendar_ajuste_das_linhas)

    def _agendar_ajuste_das_linhas(self):
        self._ajuste_das_linhas.start()

    def carregar_historico(self):
        """Preenche a tabela com os eventos gravados, do mais recente para o mais antigo."""
        try:
            eventos = EventoRepository.listar_todos()
        except (sqlite3.Error, ValueError) as erro:
            logger.error("Falha ao carregar o histórico de eventos do banco: %s", erro)
            QMessageBox.warning(
                self.janela,
                "Histórico de eventos",
                "Não foi possível carregar o histórico gravado no banco.\n"
                "Os detalhes do erro estão em logs/smartgrid.log.",
            )
            return

        self.tabela.setRowCount(len(eventos))
        for linha, evento in enumerate(eventos):
            self._preencher_linha(linha, evento)
        self._agendar_ajuste_das_linhas()
        logger.info("Histórico de eventos carregado do banco: %d registro(s).", len(eventos))

    def registrar(self, evento) -> bool:
        """Grava o evento no banco e, só depois, o mostra na tabela.

        Devolve False se a gravação falhar: nesse caso o evento não aparece na tabela,
        que sempre mostra o que está gravado no banco.
        """
        try:
            EventoRepository.inserir(evento)
        except sqlite3.Error as erro:
            logger.error("Falha ao gravar o evento '%s' no histórico: %s", evento.tipo, erro)
            # Aviso na barra de status em vez de QMessageBox: estes eventos também nascem
            # do timer da telemetria, e uma janela modal a cada falha travaria o dashboard.
            self.janela.statusBar().showMessage(
                "Falha ao gravar um evento no histórico. Detalhes em logs/smartgrid.log.",
                self.DURACAO_AVISO_MS,
            )
            return False

        self.evento_registrado.emit(evento)
        return True

    def publicar(self, evento):
        """Mostra um evento já gravado dentro de outra transação, como a do corte
        emergencial, sem gravá-lo de novo."""
        self.evento_registrado.emit(evento)

    def _adicionar_linha(self, evento):
        """Insere o evento novo no topo, mantendo a ordem do mais recente para o mais antigo."""
        self.tabela.insertRow(0)
        self._preencher_linha(0, evento)
        self.tabela.resizeRowToContents(0)

    def _preencher_linha(self, linha, evento):
        for coluna, valor in enumerate(evento.get_linha_tabela()):
            self.tabela.setItem(linha, coluna, QTableWidgetItem(valor))
