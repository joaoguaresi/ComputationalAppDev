# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDateTimeEdit,
    QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLCDNumber, QLabel,
    QMainWindow, QPushButton, QRadioButton, QSizePolicy,
    QSlider, QSpacerItem, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from pyqtgraph import PlotWidget

class Ui_JanelaPrincipal(object):
    def setupUi(self, JanelaPrincipal):
        if not JanelaPrincipal.objectName():
            JanelaPrincipal.setObjectName(u"JanelaPrincipal")
        JanelaPrincipal.resize(1200, 750)
        self.central_widget = QWidget(JanelaPrincipal)
        self.central_widget.setObjectName(u"central_widget")
        self.layout_principal = QVBoxLayout(self.central_widget)
        self.layout_principal.setSpacing(12)
        self.layout_principal.setObjectName(u"layout_principal")
        self.layout_principal.setContentsMargins(16, 16, 16, 16)
        self.label_titulo = QLabel(self.central_widget)
        self.label_titulo.setObjectName(u"label_titulo")
        self.label_titulo.setAlignment(Qt.AlignCenter)
        self.label_titulo.setStyleSheet(u"font-size: 18pt; font-weight: bold;")

        self.layout_principal.addWidget(self.label_titulo)

        self.grid_indicadores = QGridLayout()
        self.grid_indicadores.setObjectName(u"grid_indicadores")
        self.grid_indicadores.setHorizontalSpacing(16)
        self.grid_indicadores.setVerticalSpacing(4)
        self.label_tensao_titulo = QLabel(self.central_widget)
        self.label_tensao_titulo.setObjectName(u"label_tensao_titulo")
        self.label_tensao_titulo.setAlignment(Qt.AlignCenter)
        self.label_tensao_titulo.setStyleSheet(u"font-weight: bold;")

        self.grid_indicadores.addWidget(self.label_tensao_titulo, 0, 0, 1, 1)

        self.label_corrente_titulo = QLabel(self.central_widget)
        self.label_corrente_titulo.setObjectName(u"label_corrente_titulo")
        self.label_corrente_titulo.setAlignment(Qt.AlignCenter)
        self.label_corrente_titulo.setStyleSheet(u"font-weight: bold;")

        self.grid_indicadores.addWidget(self.label_corrente_titulo, 0, 1, 1, 1)

        self.label_potencia_titulo = QLabel(self.central_widget)
        self.label_potencia_titulo.setObjectName(u"label_potencia_titulo")
        self.label_potencia_titulo.setAlignment(Qt.AlignCenter)
        self.label_potencia_titulo.setStyleSheet(u"font-weight: bold;")

        self.grid_indicadores.addWidget(self.label_potencia_titulo, 0, 2, 1, 1)

        self.label_disjuntor_titulo = QLabel(self.central_widget)
        self.label_disjuntor_titulo.setObjectName(u"label_disjuntor_titulo")
        self.label_disjuntor_titulo.setAlignment(Qt.AlignCenter)
        self.label_disjuntor_titulo.setStyleSheet(u"font-weight: bold;")

        self.grid_indicadores.addWidget(self.label_disjuntor_titulo, 0, 3, 1, 1)

        self.lcd_tensao = QLCDNumber(self.central_widget)
        self.lcd_tensao.setObjectName(u"lcd_tensao")
        self.lcd_tensao.setMinimumSize(QSize(0, 70))
        self.lcd_tensao.setDigitCount(6)
        self.lcd_tensao.setSegmentStyle(QLCDNumber.Flat)

        self.grid_indicadores.addWidget(self.lcd_tensao, 1, 0, 1, 1)

        self.lcd_corrente = QLCDNumber(self.central_widget)
        self.lcd_corrente.setObjectName(u"lcd_corrente")
        self.lcd_corrente.setMinimumSize(QSize(0, 70))
        self.lcd_corrente.setDigitCount(6)
        self.lcd_corrente.setSegmentStyle(QLCDNumber.Flat)

        self.grid_indicadores.addWidget(self.lcd_corrente, 1, 1, 1, 1)

        self.lcd_potencia = QLCDNumber(self.central_widget)
        self.lcd_potencia.setObjectName(u"lcd_potencia")
        self.lcd_potencia.setMinimumSize(QSize(0, 70))
        self.lcd_potencia.setDigitCount(6)
        self.lcd_potencia.setSegmentStyle(QLCDNumber.Flat)

        self.grid_indicadores.addWidget(self.lcd_potencia, 1, 2, 1, 1)

        self.label_disjuntor_status = QLabel(self.central_widget)
        self.label_disjuntor_status.setObjectName(u"label_disjuntor_status")
        self.label_disjuntor_status.setMinimumSize(QSize(180, 70))
        self.label_disjuntor_status.setAlignment(Qt.AlignCenter)
        self.label_disjuntor_status.setWordWrap(True)
        self.label_disjuntor_status.setStyleSheet(u"background-color: #2ECC71; color: white; border-radius: 6px; padding: 6px; font-weight: bold;")

        self.grid_indicadores.addWidget(self.label_disjuntor_status, 1, 3, 1, 1)


        self.layout_principal.addLayout(self.grid_indicadores)

        self.layout_paineis = QHBoxLayout()
        self.layout_paineis.setSpacing(16)
        self.layout_paineis.setObjectName(u"layout_paineis")
        self.group_comandos = QGroupBox(self.central_widget)
        self.group_comandos.setObjectName(u"group_comandos")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.group_comandos.sizePolicy().hasHeightForWidth())
        self.group_comandos.setSizePolicy(sizePolicy)
        self.grid_comandos = QGridLayout(self.group_comandos)
        self.grid_comandos.setObjectName(u"grid_comandos")
        self.grid_comandos.setHorizontalSpacing(12)
        self.grid_comandos.setVerticalSpacing(8)
        self.label_setpoint = QLabel(self.group_comandos)
        self.label_setpoint.setObjectName(u"label_setpoint")

        self.grid_comandos.addWidget(self.label_setpoint, 0, 0, 1, 1)

        self.spin_setpoint = QDoubleSpinBox(self.group_comandos)
        self.spin_setpoint.setObjectName(u"spin_setpoint")
        self.spin_setpoint.setMinimum(10.000000000000000)
        self.spin_setpoint.setMaximum(360.000000000000000)
        self.spin_setpoint.setSingleStep(10.000000000000000)
        self.spin_setpoint.setDecimals(1)
        self.spin_setpoint.setValue(250.000000000000000)

        self.grid_comandos.addWidget(self.spin_setpoint, 0, 1, 1, 1)

        self.slider_setpoint = QSlider(self.group_comandos)
        self.slider_setpoint.setObjectName(u"slider_setpoint")
        self.slider_setpoint.setMinimum(10)
        self.slider_setpoint.setMaximum(360)
        self.slider_setpoint.setSingleStep(10)
        self.slider_setpoint.setPageStep(50)
        self.slider_setpoint.setValue(250)
        self.slider_setpoint.setOrientation(Qt.Horizontal)

        self.grid_comandos.addWidget(self.slider_setpoint, 1, 0, 1, 2)

        self.label_alerta_status = QLabel(self.group_comandos)
        self.label_alerta_status.setObjectName(u"label_alerta_status")
        self.label_alerta_status.setMinimumSize(QSize(0, 40))
        self.label_alerta_status.setAlignment(Qt.AlignCenter)
        self.label_alerta_status.setWordWrap(True)
        self.label_alerta_status.setStyleSheet(u"background-color: #2ECC71; color: white; border-radius: 6px; padding: 6px; font-weight: bold;")

        self.grid_comandos.addWidget(self.label_alerta_status, 2, 0, 1, 2)

        self.btn_corte_emergencia = QPushButton(self.group_comandos)
        self.btn_corte_emergencia.setObjectName(u"btn_corte_emergencia")
        self.btn_corte_emergencia.setMinimumSize(QSize(0, 48))
        self.btn_corte_emergencia.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_corte_emergencia.setStyleSheet(u"QPushButton { background-color: #C0392B; color: white; border-radius: 6px; font-size: 12pt; font-weight: bold; }\n"
"QPushButton:hover { background-color: #E74C3C; }\n"
"QPushButton:disabled { background-color: #95A5A6; }")

        self.grid_comandos.addWidget(self.btn_corte_emergencia, 3, 0, 1, 2)

        self.btn_religar_disjuntor = QPushButton(self.group_comandos)
        self.btn_religar_disjuntor.setObjectName(u"btn_religar_disjuntor")
        self.btn_religar_disjuntor.setMinimumSize(QSize(0, 34))
        self.btn_religar_disjuntor.setEnabled(False)
        self.btn_religar_disjuntor.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.grid_comandos.addWidget(self.btn_religar_disjuntor, 4, 0, 1, 2)

        self.btn_regras_alerta = QPushButton(self.group_comandos)
        self.btn_regras_alerta.setObjectName(u"btn_regras_alerta")
        self.btn_regras_alerta.setMinimumSize(QSize(0, 34))
        self.btn_regras_alerta.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.grid_comandos.addWidget(self.btn_regras_alerta, 5, 0, 1, 2)


        self.layout_paineis.addWidget(self.group_comandos)

        self.group_serial = QGroupBox(self.central_widget)
        self.group_serial.setObjectName(u"group_serial")
        sizePolicy.setHeightForWidth(self.group_serial.sizePolicy().hasHeightForWidth())
        self.group_serial.setSizePolicy(sizePolicy)
        self.grid_serial = QGridLayout(self.group_serial)
        self.grid_serial.setObjectName(u"grid_serial")
        self.grid_serial.setHorizontalSpacing(12)
        self.grid_serial.setVerticalSpacing(8)
        self.label_porta = QLabel(self.group_serial)
        self.label_porta.setObjectName(u"label_porta")

        self.grid_serial.addWidget(self.label_porta, 0, 0, 1, 1)

        self.combo_porta = QComboBox(self.group_serial)
        self.combo_porta.setObjectName(u"combo_porta")

        self.grid_serial.addWidget(self.combo_porta, 0, 1, 1, 1)

        self.label_baudrate = QLabel(self.group_serial)
        self.label_baudrate.setObjectName(u"label_baudrate")

        self.grid_serial.addWidget(self.label_baudrate, 1, 0, 1, 1)

        self.combo_baudrate = QComboBox(self.group_serial)
        self.combo_baudrate.setObjectName(u"combo_baudrate")

        self.grid_serial.addWidget(self.combo_baudrate, 1, 1, 1, 1)

        self.label_timeout = QLabel(self.group_serial)
        self.label_timeout.setObjectName(u"label_timeout")

        self.grid_serial.addWidget(self.label_timeout, 2, 0, 1, 1)

        self.spin_timeout = QSpinBox(self.group_serial)
        self.spin_timeout.setObjectName(u"spin_timeout")
        self.spin_timeout.setMinimum(100)
        self.spin_timeout.setMaximum(10000)
        self.spin_timeout.setSingleStep(100)
        self.spin_timeout.setValue(1000)

        self.grid_serial.addWidget(self.spin_timeout, 2, 1, 1, 1)

        self.btn_conectar = QPushButton(self.group_serial)
        self.btn_conectar.setObjectName(u"btn_conectar")
        self.btn_conectar.setMinimumSize(QSize(0, 34))
        self.btn_conectar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.grid_serial.addWidget(self.btn_conectar, 3, 0, 1, 1)

        self.btn_desconectar = QPushButton(self.group_serial)
        self.btn_desconectar.setObjectName(u"btn_desconectar")
        self.btn_desconectar.setMinimumSize(QSize(0, 34))
        self.btn_desconectar.setEnabled(False)
        self.btn_desconectar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.grid_serial.addWidget(self.btn_desconectar, 3, 1, 1, 1)

        self.label_serial_status = QLabel(self.group_serial)
        self.label_serial_status.setObjectName(u"label_serial_status")
        self.label_serial_status.setMinimumSize(QSize(0, 40))
        self.label_serial_status.setAlignment(Qt.AlignCenter)
        self.label_serial_status.setWordWrap(True)
        self.label_serial_status.setStyleSheet(u"background-color: #7F8C8D; color: white; border-radius: 6px; padding: 6px; font-weight: bold;")

        self.grid_serial.addWidget(self.label_serial_status, 4, 0, 1, 2)


        self.layout_paineis.addWidget(self.group_serial)


        self.layout_principal.addLayout(self.layout_paineis)

        self.group_grafico = QGroupBox(self.central_widget)
        self.group_grafico.setObjectName(u"group_grafico")
        self.layout_grafico = QVBoxLayout(self.group_grafico)
        self.layout_grafico.setObjectName(u"layout_grafico")
        self.layout_controles_grafico = QHBoxLayout()
        self.layout_controles_grafico.setSpacing(8)
        self.layout_controles_grafico.setObjectName(u"layout_controles_grafico")
        self.label_modo_grafico = QLabel(self.group_grafico)
        self.label_modo_grafico.setObjectName(u"label_modo_grafico")
        self.label_modo_grafico.setStyleSheet(u"font-weight: bold;")

        self.layout_controles_grafico.addWidget(self.label_modo_grafico)

        self.radio_tempo_real = QRadioButton(self.group_grafico)
        self.radio_tempo_real.setObjectName(u"radio_tempo_real")
        self.radio_tempo_real.setChecked(True)

        self.layout_controles_grafico.addWidget(self.radio_tempo_real)

        self.radio_historico = QRadioButton(self.group_grafico)
        self.radio_historico.setObjectName(u"radio_historico")

        self.layout_controles_grafico.addWidget(self.radio_historico)

        self.linha_separador_grafico = QFrame(self.group_grafico)
        self.linha_separador_grafico.setObjectName(u"linha_separador_grafico")
        self.linha_separador_grafico.setFrameShape(QFrame.Shape.VLine)
        self.linha_separador_grafico.setFrameShadow(QFrame.Shadow.Sunken)

        self.layout_controles_grafico.addWidget(self.linha_separador_grafico)

        self.widget_filtros = QWidget(self.group_grafico)
        self.widget_filtros.setObjectName(u"widget_filtros")
        self.widget_filtros.setEnabled(False)
        self.layout_filtros = QHBoxLayout(self.widget_filtros)
        self.layout_filtros.setSpacing(6)
        self.layout_filtros.setObjectName(u"layout_filtros")
        self.layout_filtros.setContentsMargins(0, 0, 0, 0)
        self.radio_ultimas = QRadioButton(self.widget_filtros)
        self.radio_ultimas.setObjectName(u"radio_ultimas")
        self.radio_ultimas.setChecked(True)

        self.layout_filtros.addWidget(self.radio_ultimas)

        self.spin_quantidade = QSpinBox(self.widget_filtros)
        self.spin_quantidade.setObjectName(u"spin_quantidade")
        self.spin_quantidade.setMinimumSize(QSize(120, 0))
        self.spin_quantidade.setMinimum(1)
        self.spin_quantidade.setMaximum(10000)
        self.spin_quantidade.setSingleStep(100)
        self.spin_quantidade.setValue(500)

        self.layout_filtros.addWidget(self.spin_quantidade)

        self.radio_intervalo = QRadioButton(self.widget_filtros)
        self.radio_intervalo.setObjectName(u"radio_intervalo")

        self.layout_filtros.addWidget(self.radio_intervalo)

        self.datetime_inicio = QDateTimeEdit(self.widget_filtros)
        self.datetime_inicio.setObjectName(u"datetime_inicio")
        self.datetime_inicio.setMinimumSize(QSize(165, 0))
        self.datetime_inicio.setEnabled(False)
        self.datetime_inicio.setCalendarPopup(True)

        self.layout_filtros.addWidget(self.datetime_inicio)

        self.label_ate = QLabel(self.widget_filtros)
        self.label_ate.setObjectName(u"label_ate")

        self.layout_filtros.addWidget(self.label_ate)

        self.datetime_fim = QDateTimeEdit(self.widget_filtros)
        self.datetime_fim.setObjectName(u"datetime_fim")
        self.datetime_fim.setMinimumSize(QSize(165, 0))
        self.datetime_fim.setEnabled(False)
        self.datetime_fim.setCalendarPopup(True)

        self.layout_filtros.addWidget(self.datetime_fim)

        self.btn_consultar = QPushButton(self.widget_filtros)
        self.btn_consultar.setObjectName(u"btn_consultar")
        self.btn_consultar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.layout_filtros.addWidget(self.btn_consultar)


        self.layout_controles_grafico.addWidget(self.widget_filtros)

        self.espacador_grafico = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout_controles_grafico.addItem(self.espacador_grafico)

        self.label_status_grafico = QLabel(self.group_grafico)
        self.label_status_grafico.setObjectName(u"label_status_grafico")
        self.label_status_grafico.setAlignment(Qt.AlignRight|Qt.AlignVCenter)

        self.layout_controles_grafico.addWidget(self.label_status_grafico)


        self.layout_grafico.addLayout(self.layout_controles_grafico)

        self.grafico_tendencia = PlotWidget(self.group_grafico)
        self.grafico_tendencia.setObjectName(u"grafico_tendencia")

        self.layout_grafico.addWidget(self.grafico_tendencia)


        self.layout_principal.addWidget(self.group_grafico)

        self.group_historico = QGroupBox(self.central_widget)
        self.group_historico.setObjectName(u"group_historico")
        self.layout_historico = QVBoxLayout(self.group_historico)
        self.layout_historico.setObjectName(u"layout_historico")
        self.tabela_historico = QTableWidget(self.group_historico)
        if (self.tabela_historico.columnCount() < 4):
            self.tabela_historico.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tabela_historico.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tabela_historico.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tabela_historico.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tabela_historico.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tabela_historico.setObjectName(u"tabela_historico")
        self.tabela_historico.setMinimumSize(QSize(0, 180))
        self.tabela_historico.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_historico.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.layout_historico.addWidget(self.tabela_historico)


        self.layout_principal.addWidget(self.group_historico)

        JanelaPrincipal.setCentralWidget(self.central_widget)

        self.retranslateUi(JanelaPrincipal)

        QMetaObject.connectSlotsByName(JanelaPrincipal)
    # setupUi

    def retranslateUi(self, JanelaPrincipal):
        JanelaPrincipal.setWindowTitle(QCoreApplication.translate("JanelaPrincipal", u"Smart Grid: Monitor de Consumo de Energia", None))
        self.label_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Monitor de Consumo de Energia - Smart Grid", None))
        self.label_tensao_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Tens\u00e3o (V)", None))
        self.label_corrente_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Corrente (A)", None))
        self.label_potencia_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Pot\u00eancia (W)", None))
        self.label_disjuntor_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Disjuntor", None))
        self.label_disjuntor_status.setText(QCoreApplication.translate("JanelaPrincipal", u"Disjuntor: FECHADO / NORMAL", None))
        self.group_comandos.setTitle(QCoreApplication.translate("JanelaPrincipal", u"Comandos e Prote\u00e7\u00e3o", None))
        self.label_setpoint.setText(QCoreApplication.translate("JanelaPrincipal", u"Setpoint de pot\u00eancia", None))
        self.spin_setpoint.setSuffix(QCoreApplication.translate("JanelaPrincipal", u" W", None))
#if QT_CONFIG(tooltip)
        self.spin_setpoint.setToolTip(QCoreApplication.translate("JanelaPrincipal", u"Limite m\u00e1ximo de pot\u00eancia monitorado pela prote\u00e7\u00e3o local (bancada: at\u00e9 12 V x 30 A = 360 W)", None))
#endif // QT_CONFIG(tooltip)
        self.label_alerta_status.setText(QCoreApplication.translate("JanelaPrincipal", u"Prote\u00e7\u00e3o: dentro do limite", None))
        self.btn_corte_emergencia.setText(QCoreApplication.translate("JanelaPrincipal", u"CORTE DE EMERG\u00caNCIA", None))
        self.btn_religar_disjuntor.setText(QCoreApplication.translate("JanelaPrincipal", u"Religar disjuntor", None))
        self.btn_regras_alerta.setText(QCoreApplication.translate("JanelaPrincipal", u"Configurar Regras de Alerta", None))
        self.group_serial.setTitle(QCoreApplication.translate("JanelaPrincipal", u"Configura\u00e7\u00e3o da Conex\u00e3o Serial", None))
        self.label_porta.setText(QCoreApplication.translate("JanelaPrincipal", u"Porta COM", None))
        self.label_baudrate.setText(QCoreApplication.translate("JanelaPrincipal", u"Baud Rate", None))
        self.label_timeout.setText(QCoreApplication.translate("JanelaPrincipal", u"Timeout", None))
        self.spin_timeout.setSuffix(QCoreApplication.translate("JanelaPrincipal", u" ms", None))
        self.btn_conectar.setText(QCoreApplication.translate("JanelaPrincipal", u"Conectar", None))
        self.btn_desconectar.setText(QCoreApplication.translate("JanelaPrincipal", u"Desconectar", None))
        self.label_serial_status.setText(QCoreApplication.translate("JanelaPrincipal", u"DESCONECTADO", None))
        self.group_grafico.setTitle(QCoreApplication.translate("JanelaPrincipal", u"Gr\u00e1fico de Tend\u00eancia", None))
        self.label_modo_grafico.setText(QCoreApplication.translate("JanelaPrincipal", u"Modo:", None))
        self.radio_tempo_real.setText(QCoreApplication.translate("JanelaPrincipal", u"Tempo real", None))
#if QT_CONFIG(tooltip)
        self.radio_tempo_real.setToolTip(QCoreApplication.translate("JanelaPrincipal", u"Curva da telemetria da placa, atualizada a cada lote de leituras", None))
#endif // QT_CONFIG(tooltip)
        self.radio_historico.setText(QCoreApplication.translate("JanelaPrincipal", u"Hist\u00f3rico", None))
#if QT_CONFIG(tooltip)
        self.radio_historico.setToolTip(QCoreApplication.translate("JanelaPrincipal", u"Curva das leituras gravadas no banco, pelo filtro ao lado", None))
#endif // QT_CONFIG(tooltip)
        self.radio_ultimas.setText(QCoreApplication.translate("JanelaPrincipal", u"\u00daltimas", None))
        self.spin_quantidade.setSuffix(QCoreApplication.translate("JanelaPrincipal", u" leituras", None))
#if QT_CONFIG(tooltip)
        self.spin_quantidade.setToolTip(QCoreApplication.translate("JanelaPrincipal", u"Quantidade de leituras gravadas (cada uma \u00e9 a m\u00e9dia de uma janela de taxa_amostragem_ms)", None))
#endif // QT_CONFIG(tooltip)
        self.radio_intervalo.setText(QCoreApplication.translate("JanelaPrincipal", u"De", None))
        self.datetime_inicio.setDisplayFormat(QCoreApplication.translate("JanelaPrincipal", u"dd/MM/yyyy HH:mm:ss", None))
        self.label_ate.setText(QCoreApplication.translate("JanelaPrincipal", u"at\u00e9", None))
        self.datetime_fim.setDisplayFormat(QCoreApplication.translate("JanelaPrincipal", u"dd/MM/yyyy HH:mm:ss", None))
        self.btn_consultar.setText(QCoreApplication.translate("JanelaPrincipal", u"Consultar", None))
        self.label_status_grafico.setText(QCoreApplication.translate("JanelaPrincipal", u"Tempo real: aguardando a placa", None))
        self.group_historico.setTitle(QCoreApplication.translate("JanelaPrincipal", u"Hist\u00f3rico de Eventos", None))
        ___qtablewidgetitem = self.tabela_historico.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("JanelaPrincipal", u"Data/Hora", None))
        ___qtablewidgetitem1 = self.tabela_historico.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("JanelaPrincipal", u"Tipo de Evento", None))
        ___qtablewidgetitem2 = self.tabela_historico.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("JanelaPrincipal", u"Descri\u00e7\u00e3o", None))
        ___qtablewidgetitem3 = self.tabela_historico.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("JanelaPrincipal", u"Valor Medido", None))
    # retranslateUi

