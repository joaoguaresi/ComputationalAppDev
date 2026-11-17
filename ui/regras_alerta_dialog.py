# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'regras_alerta_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDateEdit,
    QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget)

class Ui_RegrasAlertaDialog(object):
    def setupUi(self, RegrasAlertaDialog):
        if not RegrasAlertaDialog.objectName():
            RegrasAlertaDialog.setObjectName(u"RegrasAlertaDialog")
        RegrasAlertaDialog.resize(520, 520)
        self.layout_dialog = QVBoxLayout(RegrasAlertaDialog)
        self.layout_dialog.setObjectName(u"layout_dialog")
        self.label_instrucoes = QLabel(RegrasAlertaDialog)
        self.label_instrucoes.setObjectName(u"label_instrucoes")
        self.label_instrucoes.setWordWrap(True)

        self.layout_dialog.addWidget(self.label_instrucoes)

        self.group_formulario = QGroupBox(RegrasAlertaDialog)
        self.group_formulario.setObjectName(u"group_formulario")
        self.grid_formulario = QGridLayout(self.group_formulario)
        self.grid_formulario.setObjectName(u"grid_formulario")
        self.label_grandeza = QLabel(self.group_formulario)
        self.label_grandeza.setObjectName(u"label_grandeza")

        self.grid_formulario.addWidget(self.label_grandeza, 0, 0, 1, 1)

        self.combo_grandeza = QComboBox(self.group_formulario)
        self.combo_grandeza.setObjectName(u"combo_grandeza")

        self.grid_formulario.addWidget(self.combo_grandeza, 0, 1, 1, 1)

        self.label_limite_max = QLabel(self.group_formulario)
        self.label_limite_max.setObjectName(u"label_limite_max")

        self.grid_formulario.addWidget(self.label_limite_max, 1, 0, 1, 1)

        self.edit_limite_max = QLineEdit(self.group_formulario)
        self.edit_limite_max.setObjectName(u"edit_limite_max")

        self.grid_formulario.addWidget(self.edit_limite_max, 1, 1, 1, 1)

        self.label_vigencia = QLabel(self.group_formulario)
        self.label_vigencia.setObjectName(u"label_vigencia")

        self.grid_formulario.addWidget(self.label_vigencia, 2, 0, 1, 1)

        self.date_vigencia = QDateEdit(self.group_formulario)
        self.date_vigencia.setObjectName(u"date_vigencia")
        self.date_vigencia.setCalendarPopup(True)

        self.grid_formulario.addWidget(self.date_vigencia, 2, 1, 1, 1)

        self.btn_adicionar = QPushButton(self.group_formulario)
        self.btn_adicionar.setObjectName(u"btn_adicionar")

        self.grid_formulario.addWidget(self.btn_adicionar, 3, 0, 1, 2)


        self.layout_dialog.addWidget(self.group_formulario)

        self.group_lista = QGroupBox(RegrasAlertaDialog)
        self.group_lista.setObjectName(u"group_lista")
        self.layout_lista = QVBoxLayout(self.group_lista)
        self.layout_lista.setObjectName(u"layout_lista")
        self.lista_regras = QListWidget(self.group_lista)
        self.lista_regras.setObjectName(u"lista_regras")

        self.layout_lista.addWidget(self.lista_regras)

        self.btn_remover = QPushButton(self.group_lista)
        self.btn_remover.setObjectName(u"btn_remover")

        self.layout_lista.addWidget(self.btn_remover)


        self.layout_dialog.addWidget(self.group_lista)

        self.label_status = QLabel(RegrasAlertaDialog)
        self.label_status.setObjectName(u"label_status")
        self.label_status.setAlignment(Qt.AlignCenter)

        self.layout_dialog.addWidget(self.label_status)

        self.button_box = QDialogButtonBox(RegrasAlertaDialog)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setOrientation(Qt.Horizontal)
        self.button_box.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.layout_dialog.addWidget(self.button_box)


        self.retranslateUi(RegrasAlertaDialog)

        QMetaObject.connectSlotsByName(RegrasAlertaDialog)
    # setupUi

    def retranslateUi(self, RegrasAlertaDialog):
        RegrasAlertaDialog.setWindowTitle(QCoreApplication.translate("RegrasAlertaDialog", u"Cadastro de Regras de Alerta", None))
        self.label_instrucoes.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Cadastre os limites de seguran\u00e7a: corrente m\u00e1xima e tens\u00e3o de desarme (m\u00ednimo de duas regras). Os limites j\u00e1 salvos aparecem na lista abaixo.", None))
        self.group_formulario.setTitle(QCoreApplication.translate("RegrasAlertaDialog", u"Nova Regra", None))
        self.label_grandeza.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Grandeza", None))
        self.label_limite_max.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Limite m\u00e1ximo", None))
        self.edit_limite_max.setPlaceholderText(QCoreApplication.translate("RegrasAlertaDialog", u"N\u00famero maior que zero (ex.: 25,0)", None))
        self.label_vigencia.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Vigente a partir de", None))
        self.btn_adicionar.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Adicionar Regra", None))
        self.group_lista.setTitle(QCoreApplication.translate("RegrasAlertaDialog", u"Regras Cadastradas", None))
        self.btn_remover.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Remover Selecionada", None))
        self.label_status.setText(QCoreApplication.translate("RegrasAlertaDialog", u"Cadastre pelo menos 2 regras para continuar.", None))
    # retranslateUi

