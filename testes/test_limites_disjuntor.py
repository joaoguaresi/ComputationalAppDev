"""Testes do Bloco 4: limites e disjuntor carregados e salvos pelo DatabaseWorker.

Usam um banco temporário no lugar de data/smartgrid.db e a configuração só em memória:
o banco e o config.json de verdade não são tocados. Os slots do worker são chamados
direto, na thread do teste, e as respostas são guardadas pelos sinais.
"""

import logging
import os
import tempfile
import unittest
from contextlib import closing

from PySide6.QtCore import QCoreApplication

from controllers.database_worker import DatabaseWorker
from database.connection import Database
from models.config_manager import ConfigManager
from models.dispositivo import Dispositivo
from models.dispositivo_repository import DispositivoRepository
from models.evento_historico import EventoHistorico
from models.limite import Limite
from models.limite_repository import LimiteRepository

logging.getLogger("smartgrid").addHandler(logging.NullHandler())

app = QCoreApplication.instance() or QCoreApplication([])


class TesteBanco(unittest.TestCase):
    """Base: banco temporário criado pelo init_db() e um DatabaseWorker com a conexão aberta."""

    SINAIS = ()

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._originais = (Database.PASTA_DATA, Database.CAMINHO, ConfigManager._dados)
        Database.PASTA_DATA = self._pasta.name
        Database.CAMINHO = os.path.join(self._pasta.name, "smartgrid.db")
        ConfigManager._dados = dict(ConfigManager.DEFAULTS)
        self.assertTrue(Database.init_db())

        self.worker = DatabaseWorker()
        self.sinais = []
        for nome in self.SINAIS:
            getattr(self.worker, nome).connect(lambda *args, nome=nome: self.sinais.append((nome, args)))
        self.worker.abrir()

    def tearDown(self):
        if self.worker._conn is not None:
            self.worker._conn.close()
        Database.PASTA_DATA, Database.CAMINHO, ConfigManager._dados = self._originais
        self._pasta.cleanup()

    def recebidos(self, nome):
        return [args for sinal, args in self.sinais if sinal == nome]

    def gravar_limites_direto(self, *limites):
        """Grava como a A1/2 gravava, sem passar pela validação da bancada."""
        with closing(Database.get_connection()) as conn:
            with conn:
                for limite in limites:
                    LimiteRepository.salvar(limite, conn=conn)


class TestRevisaoDosLimites(unittest.TestCase):
    def setUp(self):
        self._config = ConfigManager._dados
        ConfigManager._dados = dict(ConfigManager.DEFAULTS)

    def tearDown(self):
        ConfigManager._dados = self._config

    def test_limite_acima_da_bancada_e_trocado_pelo_inicial(self):
        gravados = [Limite(Limite.CORRENTE_MAX, 6.0), Limite(Limite.TENSAO_DESARME, 242.0)]
        limites, corrigidos, faltando = Limite.revisar_gravados(gravados)

        valores = {limite.parametro: limite.valor for limite in limites}
        self.assertEqual(valores[Limite.CORRENTE_MAX], 6.0)  # dentro da faixa: a tabela vale
        self.assertEqual(valores[Limite.TENSAO_DESARME], ConfigManager.DEFAULTS["tensao_desarme"])
        self.assertEqual([(g.valor, i.valor) for g, i in corrigidos], [(242.0, 11.5)])
        self.assertEqual(faltando, [])

    def test_parametro_sem_limite_gravado_usa_o_inicial(self):
        limites, corrigidos, faltando = Limite.revisar_gravados([Limite(Limite.CORRENTE_MAX, 10.0)])
        self.assertEqual(faltando, [Limite.TENSAO_DESARME])
        self.assertEqual(corrigidos, [])
        self.assertEqual(len(limites), 2)

    def test_limite_no_maximo_da_bancada_vale(self):
        self.assertFalse(Limite(Limite.TENSAO_DESARME, 12.0).excede_a_bancada())
        self.assertTrue(Limite(Limite.TENSAO_DESARME, 12.01).excede_a_bancada())
        self.assertFalse(Limite(Limite.CORRENTE_MAX, 30.0).excede_a_bancada())
        self.assertTrue(Limite(Limite.CORRENTE_MAX, 30.5).excede_a_bancada())


class TestCargaDosLimites(TesteBanco):
    SINAIS = ("limites_carregados", "evento_gravado")

    def test_tabela_vazia_usa_os_iniciais_do_config(self):
        self.worker.carregar_limites()
        limites, nao_gravados, falha = self.recebidos("limites_carregados")[0]
        self.assertTrue(nao_gravados)
        self.assertEqual(falha, "")
        self.assertEqual({l.valor for l in limites}, {25.0, 11.5})
        # Nada é gravado sem o operador confirmar no QDialog.
        self.assertEqual(LimiteRepository.listar_todos(), [])

    def test_limites_da_tabela_tem_prioridade(self):
        self.gravar_limites_direto(Limite(Limite.CORRENTE_MAX, 6.0), Limite(Limite.TENSAO_DESARME, 10.0))
        self.worker.carregar_limites()
        limites, nao_gravados, _ = self.recebidos("limites_carregados")[0]
        self.assertFalse(nao_gravados)
        self.assertEqual({l.parametro: l.valor for l in limites},
                         {Limite.CORRENTE_MAX: 6.0, Limite.TENSAO_DESARME: 10.0})

    def test_242_v_da_a1_2_e_corrigido_e_regravado_com_evento(self):
        self.gravar_limites_direto(Limite(Limite.CORRENTE_MAX, 6.0), Limite(Limite.TENSAO_DESARME, 242.0))
        self.worker.carregar_limites()

        limites, nao_gravados, _ = self.recebidos("limites_carregados")[0]
        self.assertFalse(nao_gravados)
        self.assertEqual({l.parametro: l.valor for l in limites},
                         {Limite.CORRENTE_MAX: 6.0, Limite.TENSAO_DESARME: 11.5})
        # O valor corrigido foi regravado no banco ...
        self.assertEqual(LimiteRepository.buscar_por_parametro(Limite.TENSAO_DESARME).valor, 11.5)
        # ... e a correção foi para o histórico.
        (evento,), = self.recebidos("evento_gravado")
        self.assertEqual(evento.tipo, EventoHistorico.REGRAS_ALERTA)
        self.assertIn("242.00 V -> 11.50 V", evento.descricao)


class TestGravacaoDosLimites(TesteBanco):
    SINAIS = ("limites_salvos", "limites_nao_salvos")

    def test_grava_os_dois_limites(self):
        limites = [Limite(Limite.CORRENTE_MAX, 20.0), Limite(Limite.TENSAO_DESARME, 11.0)]
        self.worker.salvar_limites(limites)
        self.assertEqual(len(self.recebidos("limites_salvos")), 1)
        self.assertEqual({l.valor for l in LimiteRepository.listar_todos()}, {20.0, 11.0})

    def test_limite_acima_da_bancada_nao_chega_ao_banco(self):
        self.worker.salvar_limites([Limite(Limite.CORRENTE_MAX, 20.0), Limite(Limite.TENSAO_DESARME, 242.0)])
        (motivo,), = self.recebidos("limites_nao_salvos")
        self.assertIn("faixa da bancada", motivo)
        self.assertEqual(LimiteRepository.listar_todos(), [])

    def test_check_do_banco_desfaz_os_dois_limites(self):
        # Zero passa pela faixa da bancada, mas o CHECK (valor > 0) recusa: o ROLLBACK
        # desfaz também a corrente, gravada antes na mesma transação.
        self.worker.salvar_limites([Limite(Limite.CORRENTE_MAX, 20.0), Limite(Limite.TENSAO_DESARME, 0.0)])
        (motivo,), = self.recebidos("limites_nao_salvos")
        self.assertIn("integridade", motivo)
        self.assertEqual(LimiteRepository.listar_todos(), [])


class TestDisjuntorPeloStatusRele(TesteBanco):
    SINAIS = ("disjuntor_sincronizado", "disjuntor_nao_sincronizado")

    def test_grava_status_e_evento_juntos(self):
        evento = EventoHistorico(
            EventoHistorico.MUDANCA_DISJUNTOR, "Disjuntor aberto: a placa conectou com o relé desligado",
            dispositivo_tag=Dispositivo.TAG_DISJUNTOR_PRINCIPAL,
        )
        self.worker.sincronizar_disjuntor(Dispositivo.ABERTO, [evento])

        self.assertEqual(len(self.recebidos("disjuntor_sincronizado")), 1)
        for tag in (Dispositivo.TAG_DISJUNTOR_PRINCIPAL, Dispositivo.TAG_RELE_EMERGENCIA):
            self.assertEqual(DispositivoRepository.buscar_por_tag(tag).status, Dispositivo.ABERTO)
        self.assertIsNotNone(evento.id)

    def test_evento_recusado_desfaz_o_status(self):
        # descricao NULL viola o NOT NULL: o ROLLBACK desfaz também o status do disjuntor.
        evento = EventoHistorico(EventoHistorico.MUDANCA_DISJUNTOR, None)
        self.worker.sincronizar_disjuntor(Dispositivo.ABERTO, [evento])

        self.assertEqual(len(self.recebidos("disjuntor_nao_sincronizado")), 1)
        self.assertEqual(
            DispositivoRepository.buscar_por_tag(Dispositivo.TAG_DISJUNTOR_PRINCIPAL).status, Dispositivo.FECHADO
        )


class TestCargaDoDisjuntor(TesteBanco):
    SINAIS = ("disjuntor_carregado",)

    def test_le_o_status_gravado(self):
        DispositivoRepository.atualizar_status(Dispositivo.TAG_DISJUNTOR_PRINCIPAL, Dispositivo.ABERTO)
        self.worker.carregar_disjuntor()
        dispositivo, falha = self.recebidos("disjuntor_carregado")[0]
        self.assertEqual(falha, "")
        self.assertEqual(dispositivo.status, Dispositivo.ABERTO)

    def test_sem_conexao_avisa_a_falha(self):
        self.worker._conn.close()
        self.worker._conn = None
        self.worker.carregar_disjuntor()
        dispositivo, falha = self.recebidos("disjuntor_carregado")[0]
        self.assertIsNone(dispositivo)
        self.assertIn("conexão", falha)


if __name__ == "__main__":
    unittest.main()
