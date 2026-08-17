from PySide6.QtWidgets import QMessageBox

from models.regra_alerta import RegraAlerta
from ui.regras_alerta_dialog import Ui_RegrasAlertaDialog


class RegrasAlertaController:
    """Controla o QDialog de cadastro de regras de alerta.

    Exige o cadastro de no mínimo duas regras antes de liberar o botão OK.
    As regras cadastradas ficam disponíveis via get_regras() para a tela
    principal buscar depois que o diálogo é aceito.
    """

    MINIMO_REGRAS = 2

    GRANDEZAS = [
        (RegraAlerta.TENSAO, "Tensão (V)"),
        (RegraAlerta.CORRENTE, "Corrente (A)"),
        (RegraAlerta.POTENCIA, "Potência (W)"),
    ]

    def __init__(self, dialog, regras_iniciais=None):
        self.dialog = dialog
        self.ui = Ui_RegrasAlertaDialog()
        self.ui.setupUi(dialog)

        self.regras = list(regras_iniciais) if regras_iniciais else []

        for chave, rotulo in RegrasAlertaController.GRANDEZAS:
            self.ui.combo_grandeza.addItem(rotulo, chave)

        self._conectar_sinais()
        self._redesenhar_lista()

    def _conectar_sinais(self):
        self.ui.check_usar_limite_min.toggled.connect(self.ui.spin_limite_min.setEnabled)
        self.ui.btn_adicionar.clicked.connect(self._ao_adicionar_regra)
        self.ui.btn_remover.clicked.connect(self._ao_remover_regra)
        self.ui.button_box.accepted.connect(self._validar_antes_de_aceitar)

    def _ao_adicionar_regra(self):
        grandeza = self.ui.combo_grandeza.currentData()
        limite_max = self.ui.spin_limite_max.value()
        limite_min = self.ui.spin_limite_min.value() if self.ui.check_usar_limite_min.isChecked() else None
        descricao = self.ui.edit_descricao.text().strip()

        if not descricao:
            rotulo = self.ui.combo_grandeza.currentText()
            descricao = f"Limite de {rotulo}"

        regra = RegraAlerta(grandeza, limite_max, limite_min, descricao)
        if not regra.validar_limites():
            QMessageBox.warning(
                self.dialog,
                "Limites inválidos",
                "O limite mínimo precisa ser menor que o limite máximo.",
            )
            return

        self.regras.append(regra)
        self.ui.edit_descricao.clear()
        self._redesenhar_lista()

    def _ao_remover_regra(self):
        indice = self.ui.lista_regras.currentRow()
        if indice < 0:
            return
        del self.regras[indice]
        self._redesenhar_lista()

    def _redesenhar_lista(self):
        self.ui.lista_regras.clear()
        for regra in self.regras:
            unidade = regra.get_unidade()
            texto = f"{regra.descricao}: máx. {regra.limite_max:.2f} {unidade}"
            if regra.limite_min is not None:
                texto += f" / mín. {regra.limite_min:.2f} {unidade}"
            self.ui.lista_regras.addItem(texto)

        total = len(self.regras)
        if total < RegrasAlertaController.MINIMO_REGRAS:
            faltam = RegrasAlertaController.MINIMO_REGRAS - total
            self.ui.label_status.setText(f"Cadastre mais {faltam} regra(s) para continuar.")
        else:
            self.ui.label_status.setText(f"{total} regra(s) cadastrada(s). Pronto para confirmar.")

    def _validar_antes_de_aceitar(self):
        if len(self.regras) < RegrasAlertaController.MINIMO_REGRAS:
            QMessageBox.warning(
                self.dialog,
                "Regras insuficientes",
                f"Cadastre pelo menos {RegrasAlertaController.MINIMO_REGRAS} regras de alerta antes de confirmar.",
            )
            return
        self.dialog.accept()

    def get_regras(self) -> list:
        return list(self.regras)
