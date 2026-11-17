"""Testes do Bloco 1: protocolo do firmware e regras das leituras.

Rodar na raiz do projeto: python -m unittest
Não precisam da placa: usam linhas iguais às que o firmware envia.
"""

import unittest

from models.detector_botao import DetectorBotao
from models.leitura_telemetria import Calibracao, LeituraTelemetria, MediaMovel
from models.protocolo import (
    COMANDO_RELE_ALTERNA,
    COMANDO_RELE_LIGA,
    LinhaSerial,
    ProtocoloError,
    calcular_checksum,
    interpretar_linha,
    montar_comando_taxa,
    montar_pacote_dados,
    validar_pacote,
)
from models.rastreador_rele import RastreadorRele


class TestChecksum(unittest.TestCase):
    def test_payload_do_exemplo_do_manual(self):
        # O manual mostra 2C para este payload, mas a tabela passo a passo erra
        # em 75 XOR 44 (dá 103, não 119). O XOR correto, que o firmware envia, é 56.
        self.assertEqual(calcular_checksum("DAT,512,716,1,0"), "56")

    def test_validar_pacote_aceita_checksum_correto(self):
        self.assertEqual(validar_pacote("$DAT,512,716,1,0*56\r\n"), (True, "DAT,512,716,1,0"))

    def test_validar_pacote_recusa_checksum_errado(self):
        self.assertEqual(validar_pacote("$DAT,512,716,1,0*2C\r\n"), (False, None))

    def test_pacote_montado_e_validado_de_volta(self):
        linha = montar_pacote_dados(1023, 0, 0, 1)
        self.assertTrue(validar_pacote(linha)[0])


class TestComandos(unittest.TestCase):
    def test_comando_de_taxa(self):
        self.assertEqual(montar_comando_taxa(115200), "!S115200\n")
        self.assertEqual(montar_comando_taxa(9600), "!S9600\n")

    def test_taxa_nao_suportada(self):
        with self.assertRaises(ProtocoloError):
            montar_comando_taxa(57600)


class TestInterpretarLinha(unittest.TestCase):
    def test_dados_validos(self):
        linha = interpretar_linha("$DAT,512,716,1,0*56\r\n")
        self.assertEqual(linha.tipo, LinhaSerial.DADOS)
        self.assertEqual(linha.valor, {"a0": 512, "a1": 716, "status_rele": 1, "status_botao": 0})

    def test_um_caractere_trocado_e_descartado(self):
        with self.assertRaises(ProtocoloError):
            interpretar_linha("$DAT,512,717,1,0*56")

    def test_valores_fora_da_faixa(self):
        with self.assertRaises(ProtocoloError):
            interpretar_linha(montar_pacote_dados(1024, 512, 0, 0))
        with self.assertRaises(ProtocoloError):
            interpretar_linha(montar_pacote_dados(512, 512, 2, 0))

    def test_linhas_do_firmware(self):
        casos = {
            "PLACA EM ESPERA (9600 baud)": LinhaSerial.BANNER,
            "========================================": LinhaSerial.INFORMATIVA,
            "Envie !S115200 para iniciar nessa taxa": LinhaSerial.INFORMATIVA,
            ">>> ACK: INICIANDO EM 115200 BPS <<<": LinhaSerial.ACK_TAXA,
            "\n>>> ACK: CONVERSAO PAUSADA. RETORNANDO A 9600 BPS <<<": LinhaSerial.ACK_PAUSA,
            ">>> ACK: RELE LIGADO <<<": LinhaSerial.ACK_RELE_LIGADO,
            ">>> ACK: RELE DESLIGADO <<<": LinhaSerial.ACK_RELE_DESLIGADO,
            ">>> ACK: RELE ALTERNADO <<<": LinhaSerial.ACK_RELE_ALTERNADO,
            ">>> ERR: BAUD INVALIDO. Use 9600, 19200, 38400 ou 115200 <<<": LinhaSerial.ERR_TAXA,
            "": LinhaSerial.VAZIA,
            "ruido qualquer": LinhaSerial.DESCONHECIDA,
        }
        for texto, tipo in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(interpretar_linha(texto).tipo, tipo)

    def test_taxa_do_ack(self):
        self.assertEqual(interpretar_linha(">>> ACK: INICIANDO EM 38400 BPS <<<").valor, 38400)


class TestConversao(unittest.TestCase):
    def test_tensao_no_fundo_de_escala(self):
        self.assertAlmostEqual(Calibracao().converter_tensao(1023), 12.0)

    def test_corrente_zero_no_meio_da_escala(self):
        self.assertAlmostEqual(Calibracao().converter_corrente(512), 0.0)

    def test_corrente_positiva_e_negativa(self):
        calibracao = Calibracao()
        self.assertAlmostEqual(calibracao.converter_corrente(612), 7.405, places=2)
        self.assertAlmostEqual(calibracao.converter_corrente(412), -7.405, places=2)

    def test_leitura_aceita_potencia_negativa(self):
        campos = interpretar_linha(montar_pacote_dados(853, 400, 1, 0)).valor
        leitura = LeituraTelemetria.de_pacote(campos)
        self.assertLess(leitura.corrente_a, 0)
        self.assertLess(leitura.calcular_potencia(), 0)
        self.assertTrue(leitura.rele_ligado())

    def test_calibrar_zero(self):
        calibracao = Calibracao()
        self.assertAlmostEqual(calibracao.calibrar_zero([514, 516, 515, 515]), 515.0)
        self.assertAlmostEqual(calibracao.converter_corrente(515), 0.0)

    def test_media_movel(self):
        media = MediaMovel(janela=3)
        resultados = [media.adicionar(valor) for valor in (3, 6, 9, 12)]
        self.assertEqual(resultados, [3, 4.5, 6, 9])


class TestDetectorBotao(unittest.TestCase):
    def test_repique_nao_conta(self):
        detector = DetectorBotao(amostras_confirmacao=3)
        self.assertFalse(any(detector.atualizar(s) for s in (1, 0, 1, 1, 0)))

    def test_aperto_confirmado_conta_uma_vez(self):
        detector = DetectorBotao(amostras_confirmacao=3)
        resultados = [detector.atualizar(s) for s in (1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1)]
        self.assertEqual(resultados.count(True), 2)
        self.assertTrue(resultados[2])


class TestRastreadorRele(unittest.TestCase):
    def setUp(self):
        self.rastreador = RastreadorRele(prazo_s=2.0)
        self.assertEqual(self.rastreador.atualizar(0, agora=0.0), RastreadorRele.INICIAL)

    def test_comando_confirmado_por_ack_e_status(self):
        self.rastreador.comando_enviado(COMANDO_RELE_LIGA, agora=1.0)
        self.assertEqual(self.rastreador.atualizar(0, agora=1.1), RastreadorRele.NADA)
        self.rastreador.ack_recebido(LinhaSerial.ACK_RELE_LIGADO)
        self.assertEqual(self.rastreador.atualizar(1, agora=1.2), RastreadorRele.CONFIRMADO)

    def test_comando_sem_resposta_expira(self):
        self.rastreador.comando_enviado(COMANDO_RELE_ALTERNA, agora=1.0)
        self.assertEqual(self.rastreador.atualizar(0, agora=3.5), RastreadorRele.EXPIRADO)

    def test_mudanca_sem_comando_e_espontanea(self):
        self.assertEqual(self.rastreador.atualizar(1, agora=1.0), RastreadorRele.ESPONTANEO)
        self.assertEqual(self.rastreador.atualizar(1, agora=1.1), RastreadorRele.NADA)


if __name__ == "__main__":
    unittest.main()
