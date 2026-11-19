import logging
from collections import deque
from datetime import datetime, timedelta

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QDateTime, QObject, Qt
from PySide6.QtWidgets import QMessageBox, QSizePolicy

from models.agregador_leituras import AgregadorLeituras
from models.filtro_historico import FiltroHistorico

logger = logging.getLogger("smartgrid")


class GraficoController(QObject):
    """Gráfico de tendência da potência no dashboard.

    Fica com tudo o que é do gráfico: a configuração do PlotWidget do .ui, a curva e os
    pontos exibidos. O MainWindowController só cria o controller e entrega a ele o que
    deve ser desenhado.

    Ao abrir, o gráfico é pré-carregado com as leituras mais recentes da tabela leituras,
    pedidas ao DatabaseWorker: a consulta roda na thread do banco e a tela não espera
    por ela. Cada ponto é a média de uma janela de taxa_amostragem_ms.

    No tempo real, cada lote da thread serial (uns 20 pacotes a cada 100 ms) entra na
    curva e ela desliza: ficam os últimos JANELA_S segundos. Os pacotes entram crus, um
    ponto por $DAT, sem a média que vai para o banco.

    O seletor de modo (Tempo real / Histórico) libera os filtros do histórico: as
    últimas N leituras ou um intervalo de data/hora. O filtro é validado aqui, antes de
    qualquer consulta: um filtro inválido é recusado com QMessageBox e nunca chega ao banco.

    A consulta do histórico também roda no DatabaseWorker. Cada pedido recebe um número
    (BancoController.consultar_historico); a resposta volta com ele, e só a do último
    pedido é desenhada: se o operador consultar de novo antes da resposta, a antiga é
    descartada. Os pontos do tempo real e os do histórico ficam guardados separados, e
    trocar de modo só troca o que está desenhado. Enquanto a consulta anda, o status
    mostra "consultando..." e o cursor sobre o gráfico fica ocupado.

    O eixo X é de data/hora (DateAxisItem, no horário local): cada ponto fica no
    horário em que foi medido, e o pyqtgraph escolhe o formato pelo zoom, de
    milissegundos a dias.
    """

    # Largura do gráfico: os últimos 60 s de leituras.
    JANELA_S = 60
    # Pontos mais distantes que isso no tempo (a aplicação ficou fechada, a placa ficou
    # desconectada) não são ligados por uma reta: a curva mostra o buraco.
    LACUNA_MINIMA_S = 2.0
    COR_CURVA = "#9B59B6"
    # Teto de pontos do tempo real: 60 s a 200 pacotes por segundo (limite do firmware),
    # com folga. Protege a memória se o relógio do PC voltar e o corte por tempo falhar.
    MAXIMO_PONTOS_TEMPO_REAL = 15000
    # Intervalo sugerido ao abrir: a última hora.
    INTERVALO_INICIAL = timedelta(hours=1)

    def __init__(self, janela, ui, banco):
        super().__init__(janela)
        self.janela = janela
        self.ui = ui
        self.grafico = ui.grafico_tendencia
        self.banco = banco

        self._taxa_ms = AgregadorLeituras.do_config().taxa_ms

        # Tempo real: pontos (horário em segundos desde 1970, potência em W), do mais
        # antigo ao mais novo.
        self._pontos = deque(maxlen=self.MAXIMO_PONTOS_TEMPO_REAL)
        self._pedido_pre_carga = None
        self._recebendo = False

        # Histórico: horários, potências e quantas leituras gravadas formam cada ponto,
        # da última consulta respondida (None antes da primeira).
        self._historico = None
        self._agrupar = 1
        self._pedido_historico = None
        self._filtro_pedido = None

        # Texto e tooltip do label de status em cada modo (chave: modo_historico()).
        self._status = {False: "", True: "Escolha o filtro e clique em Consultar"}
        self._dicas = {False: "", True: ""}

        self._configurar_grafico()
        self._preparar_filtros()
        self._conectar_controles()
        self.banco.historico_consultado.connect(self._ao_consultar_historico)
        self.banco.historico_falhou.connect(self._ao_falhar_historico)
        self._pre_carregar()

    def _configurar_grafico(self):
        grafico = self.grafico
        grafico.setBackground("w")
        grafico.showGrid(x=True, y=True, alpha=0.3)
        # O eixo de data/hora lê o X como segundos desde 1970, o horário dos pontos.
        grafico.getPlotItem().setAxisItems({"bottom": pg.DateAxisItem(orientation="bottom")})
        grafico.setLabel("bottom", "Data/hora")
        grafico.setLabel("left", "Potência (W)")
        self._mostrar_janela_tempo_real(datetime.now().timestamp())

        # O status usa a largura que sobra na linha dos controles, sem alargar a janela:
        # o texto fica curto e o detalhe (o filtro consultado) vai para o tooltip.
        status = self.ui.label_status_grafico
        status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout = self.ui.layout_controles_grafico
        layout.setStretch(layout.indexOf(status), 1)

        # connect="finite": um NaN entre dois pontos interrompe a linha (ver _com_lacunas).
        self.curva_potencia = grafico.plot(pen=pg.mkPen(self.COR_CURVA, width=2), connect="finite")
        # Até 12.000 pontos no tempo real e 10.000 no histórico, redesenhados 10 vezes por
        # segundo: o pyqtgraph desenha só o trecho visível e reduz os pontos ao número de
        # pixels, mantendo os picos (mode="peak"), que são o que interessa na proteção.
        grafico.setClipToView(True)
        grafico.setDownsampling(auto=True, mode="peak")

    # ------------------------------------------------------------------
    # Seletor de modo e filtros
    # ------------------------------------------------------------------

    def _preparar_filtros(self):
        ui = self.ui
        ui.spin_quantidade.setMaximum(FiltroHistorico.QUANTIDADE_MAXIMA)
        agora = QDateTime.currentDateTime()
        ui.datetime_fim.setDateTime(agora)
        ui.datetime_inicio.setDateTime(agora.addSecs(-int(self.INTERVALO_INICIAL.total_seconds())))
        self._ao_escolher_modo()
        self._ao_escolher_filtro()

    def _conectar_controles(self):
        ui = self.ui
        ui.radio_historico.toggled.connect(self._ao_escolher_modo)
        ui.radio_intervalo.toggled.connect(self._ao_escolher_filtro)
        ui.btn_consultar.clicked.connect(self._ao_consultar)

    def modo_historico(self) -> bool:
        return self.ui.radio_historico.isChecked()

    def _ao_escolher_modo(self, *_):
        """Troca a curva desenhada. Os filtros só valem para o histórico: no tempo real
        ficam travados.

        Na primeira vez que o operador entra no histórico, o filtro da tela (as últimas
        500 leituras, por padrão) é consultado sem precisar clicar em Consultar.
        """
        historico = self.modo_historico()
        self.ui.widget_filtros.setEnabled(historico)
        if historico and self._historico is None and self._pedido_historico is None:
            self._ao_consultar()
        self._redesenhar()
        self._mostrar_status()

    def _ao_escolher_filtro(self, *_):
        """Libera só os campos do filtro escolhido: a quantidade ou as duas datas."""
        intervalo = self.ui.radio_intervalo.isChecked()
        self.ui.spin_quantidade.setEnabled(not intervalo)
        self.ui.datetime_inicio.setEnabled(intervalo)
        self.ui.datetime_fim.setEnabled(intervalo)

    def _ao_consultar(self):
        filtro = self._filtro_da_tela()
        if filtro is None:
            return
        self._consultar(filtro)

    def _consultar(self, filtro):
        """Pede a consulta ao DatabaseWorker e volta na hora: a resposta chega por
        historico_consultado com o número do pedido."""
        self._filtro_pedido = filtro
        self._pedido_historico = self.banco.consultar_historico(filtro)
        logger.info("Consulta de histórico pedida (%s).", filtro.descrever())
        self._status[True] = "Histórico: consultando..."
        self._dicas[True] = f"Consultando: {filtro.descrever()}"
        self.grafico.setCursor(Qt.BusyCursor)
        self._mostrar_status()

    def _encerrar_consulta(self):
        self._pedido_historico = None
        self.grafico.unsetCursor()

    def _filtro_da_tela(self):
        """Monta o FiltroHistorico com os campos da tela e o valida.

        Devolve None se o filtro for recusado: o operador vê o motivo num QMessageBox, o
        WARNING vai para o log e o foco volta ao campo a corrigir.
        """
        ui = self.ui
        if ui.radio_intervalo.isChecked():
            filtro = FiltroHistorico.intervalo(
                ui.datetime_inicio.dateTime().toPython(), ui.datetime_fim.dateTime().toPython()
            )
            campo = ui.datetime_inicio
        else:
            filtro = FiltroHistorico.ultimas(ui.spin_quantidade.value())
            campo = ui.spin_quantidade

        try:
            self.validar_filtro(filtro, datetime.now())
        except ValueError as erro:
            logger.warning("Filtro do histórico recusado: %s", str(erro).replace("\n", " "))
            QMessageBox.warning(self.janela, "Filtro do histórico inválido", str(erro))
            campo.setFocus()
            return None
        return filtro

    @staticmethod
    def validar_filtro(filtro, agora):
        """Levanta ValueError, com a mensagem para o operador, se o filtro não servir.

        Além das regras do FiltroHistorico (quantidade entre 1 e o máximo, início antes do
        fim), recusa um intervalo que começa no futuro: nele ainda não há leituras.
        """
        filtro.validar()
        if filtro.modo == FiltroHistorico.INTERVALO and filtro.inicio > agora:
            raise ValueError(
                "O início do intervalo está no futuro, e ainda não há leituras nesse período.\n"
                f"Início informado: {filtro.inicio.strftime(FiltroHistorico.FORMATO_DATA_HORA)}"
            )

    # ------------------------------------------------------------------
    # Pré-carga com as leituras do banco
    # ------------------------------------------------------------------

    def _pre_carregar(self):
        """Pede ao DatabaseWorker as leituras que cabem na janela do gráfico.

        Com 500 ms por linha, 60 s são as últimas 120 leituras gravadas, mesmo que sejam
        de antes de a aplicação ser fechada: o gráfico abre com a última curva conhecida.
        """
        quantidade = max(1, round(self.JANELA_S * 1000 / self._taxa_ms))
        self._pedido_pre_carga = self.banco.consultar_historico(FiltroHistorico.ultimas(quantidade))
        self._status[False] = "Carregando as últimas leituras do banco..."
        self._mostrar_status()

    def _ao_consultar_historico(self, pedido, leituras, agrupar):
        """Resposta do DatabaseWorker: da pré-carga ou da consulta do histórico."""
        if pedido == self._pedido_pre_carga:
            self._receber_pre_carga(leituras)
        elif pedido == self._pedido_historico:
            self._receber_historico(leituras, agrupar)
        # Outro número: resposta de uma consulta já substituída por uma mais nova.

    def _ao_falhar_historico(self, pedido, motivo):
        if pedido == self._pedido_pre_carga:
            self._pedido_pre_carga = None
            # O worker já registrou o ERROR no log. A pré-carga não é essencial: o gráfico
            # começa vazio e se enche com a telemetria.
            self._status[False] = "Não foi possível ler as leituras gravadas; aguardando a placa"
            self._mostrar_status()
            self.janela.statusBar().showMessage(f"Pré-carga do gráfico não feita: {motivo}.", 10000)
            return

        if pedido != self._pedido_historico:
            return
        self._encerrar_consulta()
        self._status[True] = "Histórico: a consulta falhou"
        self._mostrar_status()
        QMessageBox.warning(
            self.janela,
            "Consulta do histórico",
            f"Não foi possível consultar as {self._filtro_pedido.descrever()}.\n\n"
            f"Motivo: {motivo}\n\nOs detalhes estão em logs/smartgrid.log.",
        )

    def _receber_pre_carga(self, leituras):
        self._pedido_pre_carga = None
        # Se a placa já mandou leituras, as do banco entram só antes da primeira delas.
        primeiro = self._pontos[0][0] if self._pontos else float("inf")
        gravados = [
            (leitura.timestamp_ms / 1000, leitura.potencia_w)
            for leitura in leituras
            if leitura.timestamp_ms / 1000 < primeiro
        ]
        self._pontos.extendleft(reversed(gravados))

        if leituras:
            logger.info("Gráfico pré-carregado com %d leitura(s) do banco.", len(leituras))
        else:
            logger.info("Gráfico sem pré-carga: nenhuma leitura gravada no banco ainda.")
        if not self._recebendo:
            if leituras:
                self._status[False] = f"Últimas {len(leituras)} leituras gravadas; aguardando a placa"
            else:
                self._status[False] = "Nenhuma leitura gravada ainda; aguardando a placa"
        if not self.modo_historico():
            self._redesenhar()
        self._mostrar_status()

    def _receber_historico(self, leituras, agrupar):
        """Guarda a resposta da consulta e replota, se o operador ainda está no histórico."""
        self._encerrar_consulta()
        self._agrupar = agrupar
        self._historico = (
            np.array([leitura.timestamp_ms / 1000 for leitura in leituras], dtype=float),
            np.array([leitura.potencia_w for leitura in leituras], dtype=float),
        )

        if not leituras:
            self._status[True] = "Histórico: nenhuma leitura gravada no filtro"
        elif agrupar > 1:
            self._status[True] = f"Histórico: {len(leituras)} pontos (média de {agrupar} leituras cada)"
        else:
            self._status[True] = f"Histórico: {len(leituras)} leitura(s)"
        self._dicas[True] = f"Consulta: {self._filtro_pedido.descrever()}"

        if self.modo_historico():
            self._redesenhar()
        self._mostrar_status()

    def _mostrar_status(self):
        historico = self.modo_historico()
        self.ui.label_status_grafico.setText(self._status[historico])
        self.ui.label_status_grafico.setToolTip(self._dicas[historico])

    # ------------------------------------------------------------------
    # Tempo real pela serial
    # ------------------------------------------------------------------

    def adicionar_leituras(self, lote):
        """Lote de LeituraTelemetria da thread serial: entra na curva do tempo real.

        Os pontos continuam entrando enquanto o operador olha o histórico: ao voltar para
        o tempo real, a curva já está em dia.
        """
        if not lote:
            return
        self._pontos.extend((leitura.timestamp.timestamp(), leitura.calcular_potencia()) for leitura in lote)

        # Desliza a janela: sai o que ficou mais velho que JANELA_S segundos.
        limite = self._pontos[-1][0] - self.JANELA_S
        while self._pontos and self._pontos[0][0] < limite:
            self._pontos.popleft()

        if not self._recebendo:
            self._recebendo = True
            self._status[False] = "Tempo real: recebendo a telemetria da placa"
            self._dicas[False] = ""
            self._mostrar_status()
        if not self.modo_historico():
            self._redesenhar()

    def placa_desconectada(self, motivo=""):
        """A telemetria parou: a curva fica com o que já chegou, e o status explica."""
        self._recebendo = False
        self._status[False] = "Tempo real: placa desconectada"
        self._dicas[False] = motivo
        self._mostrar_status()

    # ------------------------------------------------------------------
    # Desenho
    # ------------------------------------------------------------------

    def _redesenhar(self):
        """Desenha a curva do modo escolhido: os pontos do tempo real ou os do histórico."""
        if self.modo_historico():
            horarios, potencias = self._historico if self._historico is not None else ([], [])
            # Cada ponto agrupado cobre "agrupar" janelas: só um buraco maior que alguns
            # pontos seguidos é uma lacuna de verdade.
            lacuna_s = max(self.LACUNA_MINIMA_S, 3 * self._agrupar * self._taxa_ms / 1000)
        else:
            quantidade = len(self._pontos)
            horarios = np.fromiter((x for x, _ in self._pontos), dtype=float, count=quantidade)
            potencias = np.fromiter((y for _, y in self._pontos), dtype=float, count=quantidade)
            lacuna_s = self.LACUNA_MINIMA_S

        if len(horarios) == 0:
            self.curva_potencia.setData([], [])
            if not self.modo_historico():
                self._mostrar_janela_tempo_real(datetime.now().timestamp())
            return

        horarios, potencias = self._com_lacunas(horarios, potencias, lacuna_s)
        self.curva_potencia.setData(horarios, potencias)
        if self.modo_historico():
            # O histórico pode cobrir de segundos a dias: o eixo X se ajusta aos dados.
            self.grafico.enableAutoRange()
        else:
            self._mostrar_janela_tempo_real(horarios[-1])

    def _mostrar_janela_tempo_real(self, ultimo_horario):
        """Eixo X do tempo real: os JANELA_S segundos que terminam na leitura mais recente."""
        self.grafico.setXRange(ultimo_horario - self.JANELA_S, ultimo_horario, padding=0)
        self.grafico.enableAutoRange(axis="y")

    @staticmethod
    def _com_lacunas(horarios, valores, lacuna_s):
        """Põe um NaN entre dois pontos separados por mais de lacuna_s segundos.

        Com connect="finite", o pyqtgraph não liga pontos através de um NaN: um período
        sem leituras aparece como um buraco na curva, e não como uma reta inventada.
        """
        if len(horarios) < 2:
            return horarios, valores
        quebras = np.nonzero(np.diff(horarios) > lacuna_s)[0] + 1
        if len(quebras) == 0:
            return horarios, valores
        # O NaN ganha o horário do ponto seguinte: o eixo X continua em ordem.
        return np.insert(horarios, quebras, horarios[quebras]), np.insert(valores, quebras, np.nan)
