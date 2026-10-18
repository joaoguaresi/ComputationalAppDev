import logging
import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from models.limite import Limite
from models.limite_repository import LimiteRepository
from ui.regras_alerta_dialog import Ui_RegrasAlertaDialog

logger = logging.getLogger("smartgrid")


class RegrasAlertaController:
    """Controla o QDialog de cadastro de regras de alerta (limites de segurança).

    Ao abrir, carrega os limites gravados na tabela limites do banco. Cada parâmetro
    (corrente máxima e tensão de desarme) tem um único limite, e o diálogo exige o
    cadastro de no mínimo duas regras antes de liberar o botão OK. Os limites
    cadastrados ficam disponíveis via get_limites() para a tela principal buscar
    depois que o diálogo é aceito.
    """

    MINIMO_REGRAS = 2

    def __init__(self, dialog):
        self.dialog = dialog
        self.ui = Ui_RegrasAlertaDialog()
        self.ui.setupUi(dialog)

        for parametro in Limite.PARAMETROS:
            rotulo = f"{Limite.NOMES[parametro]} ({Limite.UNIDADES[parametro]})"
            self.ui.combo_grandeza.addItem(rotulo, parametro)
        self.ui.date_vigencia.setDate(QDate.currentDate())

        self.limites = self._carregar_limites_salvos()

        self._conectar_sinais()
        self._redesenhar_lista()

    def _carregar_limites_salvos(self) -> list:
        """Lê os limites gravados no banco para mostrá-los na lista ao abrir o diálogo."""
        try:
            limites = LimiteRepository.listar_todos()
        except sqlite3.Error as erro:
            logger.error("Falha ao carregar os limites de segurança do banco: %s", erro)
            QMessageBox.warning(
                self.dialog,
                "Limites de segurança",
                "Não foi possível carregar os limites gravados no banco.\n"
                "Os detalhes do erro estão em logs/smartgrid.log.",
            )
            return []

        logger.info("Limites de segurança carregados do banco: %d registro(s).", len(limites))
        return limites

    def _conectar_sinais(self):
        self.ui.btn_adicionar.clicked.connect(self._ao_adicionar_regra)
        self.ui.btn_remover.clicked.connect(self._ao_remover_regra)
        self.ui.button_box.accepted.connect(self._validar_antes_de_aceitar)
        self.ui.button_box.rejected.connect(self.dialog.reject)

    def _ao_adicionar_regra(self):
        parametro = self.ui.combo_grandeza.currentData()
        novo = Limite(parametro, self.ui.spin_limite_max.value())

        # O parametro é UNIQUE no banco: um valor novo para um parâmetro que já está na
        # lista substitui o anterior, em vez de criar uma segunda regra para ele.
        self.limites = [limite for limite in self.limites if limite.parametro != parametro]
        self.limites.append(novo)
        self.limites.sort(key=lambda limite: limite.parametro)
        self._redesenhar_lista()

    def _ao_remover_regra(self):
        indice = self.ui.lista_regras.currentRow()
        if indice < 0:
            return
        del self.limites[indice]
        self._redesenhar_lista()

    def _redesenhar_lista(self):
        self.ui.lista_regras.clear()
        for limite in self.limites:
            self.ui.lista_regras.addItem(f"{limite.get_nome()}: {limite.get_valor_formatado()}")

        total = len(self.limites)
        if total < RegrasAlertaController.MINIMO_REGRAS:
            faltam = RegrasAlertaController.MINIMO_REGRAS - total
            self.ui.label_status.setText(f"Cadastre mais {faltam} regra(s) para continuar.")
        else:
            self.ui.label_status.setText(f"{total} regra(s) cadastrada(s). Pronto para confirmar.")

    def _validar_antes_de_aceitar(self):
        if len(self.limites) < RegrasAlertaController.MINIMO_REGRAS:
            QMessageBox.warning(
                self.dialog,
                "Regras insuficientes",
                f"Cadastre pelo menos {RegrasAlertaController.MINIMO_REGRAS} regras de alerta antes de confirmar.",
            )
            return
        self.dialog.accept()

    def get_limites(self) -> list:
        return list(self.limites)
