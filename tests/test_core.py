from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import armazenamento
import nfe
import roteamento
from extrator_chave import chave_nfe_valida, localizar_chave
from roteamento import carregar_empresas
from xml_fiscal import extrair_dados_xml


CHAVE_EXEMPLO = "43260111111111000191550010000000011000000005"


class TesteExtracao(unittest.TestCase):
    def test_chave_nfe_agrupada(self):
        texto = (
            "CHAVE DE ACESSO\n"
            "4326 0111 1111 1100 0191 5500 1000 0000 0110 0000 0005"
        )
        self.assertTrue(chave_nfe_valida(CHAVE_EXEMPLO))
        self.assertEqual(localizar_chave(texto), (CHAVE_EXEMPLO, "NFE"))

    def test_chave_nfse_nacional(self):
        chave = "1" * 50
        self.assertEqual(
            localizar_chave(f"CHAVE DE ACESSO\n{chave}"),
            (chave, "NFSE"),
        )

    def test_destino_nfe_configuravel(self):
        original_base = armazenamento.DESTINO_NFE
        original_subpasta = armazenamento.CRIAR_SUBPASTA_DOCUMENTO
        try:
            with tempfile.TemporaryDirectory() as pasta:
                armazenamento.DESTINO_NFE = Path(pasta) / "nfe"
                armazenamento.CRIAR_SUBPASTA_DOCUMENTO = True
                destino = armazenamento.montar_destino_local(
                    Path(f"{CHAVE_EXEMPLO}.xml"),
                    "11.111.111/1111-11",
                    "NFE",
                )
                self.assertEqual(
                    destino,
                    Path(pasta) / "nfe" / "11111111111111" / f"{CHAVE_EXEMPLO}.xml",
                )
        finally:
            armazenamento.DESTINO_NFE = original_base
            armazenamento.CRIAR_SUBPASTA_DOCUMENTO = original_subpasta

    def test_destino_sem_subpasta(self):
        original_base = armazenamento.DESTINO_NFSE
        original_subpasta = armazenamento.CRIAR_SUBPASTA_DOCUMENTO
        try:
            with tempfile.TemporaryDirectory() as pasta:
                armazenamento.DESTINO_NFSE = Path(pasta) / "nfse"
                armazenamento.CRIAR_SUBPASTA_DOCUMENTO = False
                destino = armazenamento.montar_destino_local(
                    Path("nota.xml"),
                    "22222222222222",
                    "NFSE",
                )
                self.assertEqual(destino, Path(pasta) / "nfse" / "nota.xml")
        finally:
            armazenamento.DESTINO_NFSE = original_base
            armazenamento.CRIAR_SUBPASTA_DOCUMENTO = original_subpasta

    def test_copia_xml(self):
        original_base = armazenamento.DESTINO_NFE
        original_subpasta = armazenamento.CRIAR_SUBPASTA_DOCUMENTO
        try:
            with tempfile.TemporaryDirectory() as pasta:
                raiz = Path(pasta)
                origem = raiz / "origem.xml"
                origem.write_text("<xml>teste</xml>", encoding="utf-8")
                armazenamento.DESTINO_NFE = raiz / "destino"
                armazenamento.CRIAR_SUBPASTA_DOCUMENTO = True

                resultado = armazenamento.salvar_xml(
                    origem,
                    "11111111111111",
                    "NFE",
                )
                destino = Path(resultado["arquivo_destino"])
                self.assertTrue(destino.is_file())
                self.assertEqual(destino.read_text(encoding="utf-8"), "<xml>teste</xml>")
        finally:
            armazenamento.DESTINO_NFE = original_base
            armazenamento.CRIAR_SUBPASTA_DOCUMENTO = original_subpasta

    def test_json_tolera_nbsp_e_cnpj_repetido(self):
        original = roteamento.EMPRESAS_CERTIFICADAS_ARQUIVO
        try:
            with tempfile.TemporaryDirectory() as pasta:
                arquivo = Path(pasta) / "empresas.json"
                arquivo.write_text(
                    '[\u00a0{"cnpj":"11111111111111","nome":"Nome antigo"},'
                    '{"cnpj":"11111111111111","nome":"Nome final"}]',
                    encoding="utf-8",
                )
                roteamento.EMPRESAS_CERTIFICADAS_ARQUIVO = arquivo
                empresas = carregar_empresas()
            self.assertEqual(empresas, {"11111111111111": "Nome final"})
        finally:
            roteamento.EMPRESAS_CERTIFICADAS_ARQUIVO = original

    def test_erro_script_explica_que_json_nao_baixa_xml(self):
        originais = (
            nfe.NFE_XML_DIR,
            nfe.PHP_EXE,
            nfe.NFE_SCRIPT_EMITIDA,
            nfe.NFE_CNPJS_EMITENTES_PROPRIOS,
        )
        try:
            with tempfile.TemporaryDirectory() as pasta:
                nfe.NFE_XML_DIR = Path(pasta)
                nfe.PHP_EXE = Path(sys.executable)
                nfe.NFE_SCRIPT_EMITIDA = Path(pasta) / "ausente.php"
                nfe.NFE_CNPJS_EMITENTES_PROPRIOS = {"11111111000191"}
                status, detalhe, xml = nfe.consultar_nfe(CHAVE_EXEMPLO)
            self.assertEqual(status, "ERRO_SCRIPT_NFE")
            self.assertIsNone(xml)
            self.assertIn("empresas_certificadas.json", detalhe)
            self.assertIn("NFE_SCRIPT_EMITIDA", detalhe)
        finally:
            (
                nfe.NFE_XML_DIR,
                nfe.PHP_EXE,
                nfe.NFE_SCRIPT_EMITIDA,
                nfe.NFE_CNPJS_EMITENTES_PROPRIOS,
            ) = originais

    def test_destinatario_extraido_do_xml_nfe(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
          <NFe><infNFe>
            <ide><nNF>123</nNF></ide>
            <emit><CNPJ>11111111111111</CNPJ><xNome>EMPRESA EXEMPLO</xNome></emit>
            <dest><CNPJ>22222222222222</CNPJ><xNome>DESTINATARIO EXEMPLO</xNome></dest>
          </infNFe></NFe>
        </nfeProc>"""
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "nota.xml"
            caminho.write_text(xml, encoding="utf-8")
            dados = extrair_dados_xml(caminho, "NFE")
        self.assertEqual(dados["cnpj_emitente"], "11111111111111")
        self.assertEqual(dados["cnpj_destinatario"], "22222222222222")
        self.assertEqual(dados["tipo"], "NFE")


if __name__ == "__main__":
    unittest.main()
