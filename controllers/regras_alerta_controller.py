import logging
import math

from PySide6.QtCore import QDate, QObject
from PySide6.QtWidgets import QMessageBox

from models.limite import Limite
from ui.regras_alerta_dialog import Ui_RegrasAlertaDialog

logger = logging.getLogger("smartgrid")


class RegrasAlertaController(QObject):
    """Controla o QDialog de cadastro de regras de alerta (limites de segurança).

    Abre com os limites que o dashboard monitora agora (os da tabela limites, já lidos
    pelo DatabaseWorker). Cada parâmetro (corrente máxima e tensão de desarme) tem um
    único limite, e o diálogo exige o cadastro de no mínimo duas regras antes de liberar
    o botão OK. Todo valor digitado é validado aqui, no controller, antes de entrar na
    lista, inclusive contra a faixa da bancada (até 12 V e 30 A).

    No OK, os limites vão para o DatabaseWorker, que os grava numa única transação. O
    diálogo fica aberto, com os botões travados, até a resposta: fecha quando o banco
    confirma e continua aberto para correção quando ele recusa.
    """

    MINIMO_REGRAS = 2

    def __init__(self, dialog, banco, limites, limites_nao_gravados=False):
        super().__init__(dialog)
        self.dialog = dialog
        self.banco = banco
        self.ui = Ui_RegrasAlertaDialog()
        self.ui.setupUi(dialog)

        for parametro in Limite.PARAMETROS:
            rotulo = f"{Limite.NOMES[parametro]} ({Limite.UNIDADES[parametro]})"
            self.ui.combo_grandeza.addItem(rotulo, parametro)
        self.ui.date_vigencia.setDate(QDate.currentDate())

        # True quando algum limite da lista veio do config.json (tabela limites vazia ou
        # incompleta): os valores aparecem para o operador, mas só são gravados no banco
        # quando ele confirma.
        self.limites_do_config = limites_nao_gravados
        self.limites = sorted(limites, key=lambda limite: limite.parametro)
        self._salvando = False

        self._conectar_sinais()
        self._redesenhar_lista()

    def _conectar_sinais(self):
        self.ui.btn_adicionar.clicked.connect(self._adicionar_valor_digitado)
        self.ui.btn_remover.clicked.connect(self._ao_remover_regra)
        self.ui.button_box.accepted.connect(self._validar_antes_de_aceitar)
        self.ui.button_box.rejected.connect(self.dialog.reject)
        self.banco.limites_salvos.connect(self._ao_salvar_limites)
        self.banco.limites_nao_salvos.connect(self._ao_recusar_limites)

    def desligar(self):
        """Desliga as respostas do banco quando o diálogo fecha."""
        self.banco.limites_salvos.disconnect(self._ao_salvar_limites)
        self.banco.limites_nao_salvos.disconnect(self._ao_recusar_limites)

    def _adicionar_valor_digitado(self) -> bool:
        """Valida o valor digitado e, se ele for válido, inclui o limite na lista.

        Devolve False quando o valor é recusado: nesse caso nada entra na lista e, por
        isso, nada é gravado no banco.
        """
        parametro = self.ui.combo_grandeza.currentData()
        valor = self._validar_valor(self.ui.edit_limite_max.text().strip(), parametro)
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

    def _validar_valor(self, texto, parametro):
        """Converte o texto digitado no valor do limite, ou devolve None se ele for inválido.

        A validação segue esta ordem: campo vazio, valor não numérico, valor zero ou
        negativo e valor acima da faixa da bancada. Cada falha avisa o operador com
        QMessageBox e registra WARNING no log.
        """
        nome = Limite.NOMES[parametro].lower()
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

        maximo = Limite.MAXIMOS[parametro]
        if valor > maximo:
            unidade = Limite.UNIDADES[parametro]
            self._recusar_entrada(
                "Valor acima da faixa da bancada",
                f"O limite de {nome} precisa ser no máximo {maximo:.2f} {unidade}: a bancada "
                "trabalha com 0 a 12 V e ±30 A, e um limite acima disso nunca dispararia.\n"
                f"Valor informado: {texto}",
                f"valor {texto} acima da faixa da bancada, máximo {maximo:.2f} {unidade} ({nome})",
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
        elif self.limites_do_config:
            self.ui.label_status.setText(
                "Limites iniciais do config.json, ainda não salvos. Confirme com OK para gravá-los."
            )
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

        self._salvar_limites()

    def _salvar_limites(self):
        """Pede ao DatabaseWorker a gravação de todos os limites da lista numa única
        transação (ou todos, ou nenhum) e trava os botões até a resposta.

        O diálogo continua respondendo enquanto o banco grava: a gravação roda na thread
        do banco. A resposta chega por limites_salvos ou limites_nao_salvos.
        """
        self._salvando = True
        self._travar_edicao(True)
        self.ui.label_status.setText("Gravando os limites no banco...")
        self.banco.salvar_limites(self.limites)

    def _ao_salvar_limites(self, _limites):
        """O banco confirmou o COMMIT: o diálogo fecha. O LimitesController, que também
        recebe este sinal, passa a monitorar os limites novos."""
        if not self._salvando:
            return
        self._salvando = False
        self.dialog.accept()

    def _ao_recusar_limites(self, motivo):
        """O banco recusou a gravação (CHECK, faixa da bancada ou banco ocupado): o ROLLBACK
        já desfez tudo, e o diálogo continua aberto para a correção."""
        if not self._salvando:
            return
        self._salvando = False
        self._travar_edicao(False)
        self._redesenhar_lista()
        QMessageBox.critical(
            self.dialog,
            "Limites não salvos",
            "Não foi possível gravar os limites no banco.\n"
            f"Motivo: {motivo}\n\n"
            "A transação foi desfeita (ROLLBACK) e nenhum limite foi alterado. Corrija e tente novamente.",
        )

    def _travar_edicao(self, travar):
        for widget in (self.ui.button_box, self.ui.btn_adicionar, self.ui.btn_remover,
                       self.ui.edit_limite_max, self.ui.combo_grandeza):
            widget.setEnabled(not travar)

    def get_limites(self) -> list:
        return list(self.limites)
