
from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QGridLayout, QGroupBox, QLCDNumber,
    QLabel, QMainWindow, QSizePolicy, QVBoxLayout,
    QWidget)

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

        self.group_grafico = QGroupBox(self.central_widget)
        self.group_grafico.setObjectName(u"group_grafico")
        self.layout_grafico = QVBoxLayout(self.group_grafico)
        self.layout_grafico.setObjectName(u"layout_grafico")
        self.grafico_tendencia = PlotWidget(self.group_grafico)
        self.grafico_tendencia.setObjectName(u"grafico_tendencia")

        self.layout_grafico.addWidget(self.grafico_tendencia)


        self.layout_principal.addWidget(self.group_grafico)

        JanelaPrincipal.setCentralWidget(self.central_widget)

        self.retranslateUi(JanelaPrincipal)

        QMetaObject.connectSlotsByName(JanelaPrincipal)
    # setupUi

    def retranslateUi(self, JanelaPrincipal):
        JanelaPrincipal.setWindowTitle(QCoreApplication.translate("JanelaPrincipal", u"Smart Grid \u2014 Monitor de Consumo de Energia", None))
        self.label_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Monitor de Consumo de Energia \u2014 Smart Grid", None))
        self.label_tensao_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Tens\u00e3o (V)", None))
        self.label_corrente_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Corrente (A)", None))
        self.label_potencia_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Pot\u00eancia (W)", None))
        self.label_disjuntor_titulo.setText(QCoreApplication.translate("JanelaPrincipal", u"Disjuntor", None))
        self.label_disjuntor_status.setText(QCoreApplication.translate("JanelaPrincipal", u"Disjuntor: FECHADO / NORMAL", None))
        self.group_grafico.setTitle(QCoreApplication.translate("JanelaPrincipal", u"Gr\u00e1fico de Tend\u00eancia", None))
    # retranslateUi

