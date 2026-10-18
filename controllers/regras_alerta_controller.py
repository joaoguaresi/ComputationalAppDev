import logging
import math
import sqlite3
from contextlib import closing

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from database.connection import Database
from models.limite import Limite
from models.limite_repository import LimiteRepository
from ui.regras_alerta_dialog import Ui_RegrasAlertaDialog

logger = logging.getLogger("smartgrid")


class RegrasAlertaController:
    """Controla o QDialog de cadastro de regras de alerta (limites de segurança).

    Ao abrir, carrega os limites gravados na tabela limites do banco. Cada parâmetro
    (corrente máxima e tensão de desarme) tem um único limite, e o diálogo exige o
    cadastro de no mínimo duas regras antes de liberar o botão OK. Todo valor digitado
    é validado aqui, no controller, antes de entrar na lista. No OK, os limites são
    gravados no banco numa única transação e ficam disponíveis via get_limites() para
    a tela principal buscar depois que o diálogo é aceito.
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
        self.ui.btn_adicionar.clicked.connect(self._adicionar_valor_digitado)
        self.ui.btn_remover.clicked.connect(self._ao_remover_regra)
        self.ui.button_box.accepted.connect(self._validar_antes_de_aceitar)
        self.ui.button_box.rejected.connect(self.dialog.reject)

    def _adicionar_valor_digitado(self) -> bool:
        """Valida o valor digitado e, se ele for válido, inclui o limite na lista.

        Devolve False quando o valor é recusado: nesse caso nada entra na lista e, por
        isso, nada é gravado no banco.
        """
        parametro = self.ui.combo_grandeza.currentData()
        valor = self._validar_valor(self.ui.edit_limite_max.text().strip(), Limite.NOMES[parametro].lower())
        if valor is None:
            return False

        # O parametro é UNIQUE no banco: um valor novo para um parâmetro que já está na
        # lista substitui o anterior, em vez de criar uma segunda regra para ele.
        self.limites = [limite for limite in self.limites if limite.parametro != parametro]
        self.limites.append(Limite(parametro, valor))
        self.limites.sort(key=lambda limite: limite.parametro)

        self.ui.edit_limite_max.clear()
        self._redesenhar_lista()
        return True

    def _validar_valor(self, texto, nome):
        """Converte o texto digitado no valor do limite, ou devolve None se ele for inválido.

        A validação segue esta ordem: campo vazio, valor não numérico e valor zero ou
        negativo. Cada falha avisa o operador com QMessageBox e registra WARNING no log.
        """
        if not texto:
            self._recusar_entrada(
                "Campo vazio",
                f"Preencha o valor do limite de {nome}.",
                f"campo vazio ({nome})",
            )
            return None

        try:
            # Aceita vírgula decimal, como o operador costuma digitar (25,5).
            valor = float(texto.replace(",", "."))
            # float() também aceita 'inf' e 'nan', que não servem como limite.
            if not math.isfinite(valor):
                raise ValueError(texto)
        except ValueError:
            self._recusar_entrada(
                "Valor não numérico",
                f"O valor '{texto}' não é um número.\n"
                "Digite apenas números, com vírgula ou ponto nos decimais (ex.: 25,0).",
                f"valor '{texto}' não numérico ({nome})",
            )
            return None

        if valor <= 0:
            self._recusar_entrada(
                "Valor inválido",
                f"O limite de {nome} precisa ser maior que zero.\nValor informado: {texto}",
                f"valor {texto} menor ou igual a zero ({nome})",
            )
            return None

        return valor

    def _recusar_entrada(self, titulo, mensagem, motivo):
        """Registra a entrada inválida no log, avisa o operador e devolve o foco ao campo
        para a correção."""
        logger.warning("Entrada inválida no cadastro de limites: %s.", motivo)
        QMessageBox.warning(self.dialog, titulo, mensagem)
        self.ui.edit_limite_max.setFocus()
        self.ui.edit_limite_max.selectAll()

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
        # Um valor digitado e não adicionado passa pela mesma validação antes de
        # confirmar: assim o OK (ou o Enter no campo) nem ignora o valor sem aviso, nem
        # aceita um valor inválido.
        if self.ui.edit_limite_max.text().strip() and not self._adicionar_valor_digitado():
            return

        if len(self.limites) < RegrasAlertaController.MINIMO_REGRAS:
            QMessageBox.warning(
                self.dialog,
                "Regras insuficientes",
                f"Cadastre pelo menos {RegrasAlertaController.MINIMO_REGRAS} regras de alerta antes de confirmar.",
            )
            return

        if not self._salvar_limites():
            return
        self.dialog.accept()

    def _salvar_limites(self) -> bool:
        """Grava todos os limites da lista numa única transação: ou todos, ou nenhum.

        Cada LimiteRepository.salvar recebe a mesma conexão e não faz commit. O with conn:
        faz o COMMIT só no fim do bloco; se qualquer limite falhar, o ROLLBACK desfaz os
        que já tinham sido gravados, e o diálogo continua aberto para a correção.
        """
        try:
            with closing(Database.get_connection()) as conn:
                with conn:
                    for limite in self.limites:
                        LimiteRepository.salvar(limite, conn=conn)
        except sqlite3.IntegrityError as erro:
            # Segunda barreira: a validação do controller já recusa zero, negativo e
            # texto, mas o CHECK da tabela recusa de novo qualquer valor que escape dela.
            logger.error("Limites de segurança recusados pelo banco. Rollback executado: %s.", erro)
            QMessageBox.critical(
                self.dialog,
                "Limites não salvos",
                "O banco recusou os limites por violarem uma restrição de integridade.\n"
                f"Motivo: {erro}\n\n"
                "A transação foi desfeita (ROLLBACK) e nenhum limite foi alterado.",
            )
            return False
        except sqlite3.Error as erro:
            # OperationalError (ex.: database is locked, quando o timeout da conexão se
            # esgota) e as demais falhas do SQLite.
            logger.error("Falha ao salvar os limites de segurança, nenhum limite foi alterado: %s.", erro)
            QMessageBox.critical(
                self.dialog,
                "Limites não salvos",
                "Não foi possível gravar os limites no banco.\n"
                f"Motivo: {erro}\n\n"
                "Nenhum limite foi alterado. Tente novamente.",
            )
            return False

        resumo = ", ".join(f"{limite.get_nome().lower()} {limite.get_valor_formatado()}" for limite in self.limites)
        logger.info("Limites de segurança salvos no banco: %s.", resumo)
        return True

    def get_limites(self) -> list:
        return list(self.limites)
