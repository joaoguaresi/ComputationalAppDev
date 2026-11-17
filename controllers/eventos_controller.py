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

    Os eventos novos são gravados pelo DatabaseWorker, na thread do banco: registrar()
    só faz o pedido, e a linha entra na tabela quando o worker confirma a gravação.
    """

    LARGURA_DATA_HORA = 150
    LARGURA_TIPO = 180
    DURACAO_AVISO_MS = 10000

    # Emitido depois que o evento foi gravado no banco.
    evento_registrado = Signal(object)

    def __init__(self, janela, tabela, banco):
        super().__init__(janela)
        self.janela = janela
        self.tabela = tabela
        self.banco = banco

        self._configurar_colunas()
        self.evento_registrado.connect(self._adicionar_linha)
        self.banco.evento_gravado.connect(self.evento_registrado)
        self.banco.evento_nao_gravado.connect(self._avisar_falha_na_gravacao)

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

    def registrar(self, evento):
        """Pede ao DatabaseWorker que grave o evento e volta na hora.

        O evento só aparece na tabela quando o worker confirma a gravação (evento_gravado).
        Se ela falhar, ele não aparece: a tabela sempre mostra o que está gravado no banco.
        """
        self.banco.registrar_evento(evento)

    def _avisar_falha_na_gravacao(self, evento, motivo):
        # O worker já registrou o ERROR no log. Aviso na barra de status em vez de
        # QMessageBox: estes eventos também nascem da telemetria, e uma janela modal a
        # cada falha travaria o dashboard.
        self.janela.statusBar().showMessage(
            f"Falha ao gravar o evento '{evento.tipo}' no histórico. Detalhes em logs/smartgrid.log.",
            self.DURACAO_AVISO_MS,
        )

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
