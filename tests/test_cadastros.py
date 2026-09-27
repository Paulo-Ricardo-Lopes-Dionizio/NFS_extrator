from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import cadastros
import fila_bot
import historico


class TesteCadastros(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        pasta = Path(self.temp.name)
        self.db_cadastros_original = cadastros.DB_CADASTROS
        self.db_fila_original = fila_bot.DB_FILA
        self.db_historico_original = historico.DB
        cadastros.DB_CADASTROS = pasta / "cadastros.sqlite3"
        fila_bot.DB_FILA = pasta / "fila.sqlite3"
        historico.DB = pasta / "historico.sqlite3"
        cadastros.inicializar_cadastros()
        fila_bot.inicializar_fila()
        historico.inicializar()

    def tearDown(self):
        cadastros.DB_CADASTROS = self.db_cadastros_original
        fila_bot.DB_FILA = self.db_fila_original
        historico.DB = self.db_historico_original
        self.temp.cleanup()

    def test_user_id_estavel_atualiza_chat_sem_duplicar(self):
        cadastros.atualizar_perfil_telegram(
            telegram_user_id=123,
            chat_id=1000,
            username="Usuario",
            first_name="nome",
            last_name="sobrenome",
            language_code="pt-br",
        )
        cadastros.salvar_cadastro(123, "Setor", "Nome sobrenome")

        # Simula conversa apagada e um novo chat/perfil atualizado.
        cadastros.atualizar_perfil_telegram(
            telegram_user_id=123,
            chat_id=2000,
            username="usuario_novo",
            first_name="nome",
            last_name="sobrenome",
            language_code="pt-br",
        )
        registro = cadastros.obter_cadastro(123)
        self.assertEqual(registro["ultimo_chat_id"], 2000)
        self.assertEqual(registro["setor"], "Setor")
        self.assertEqual(registro["nome_completo"], "Nome sobrenome")

        with sqlite3.connect(cadastros.DB_CADASTROS) as con:
            total = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        self.assertEqual(total, 1)

    def test_mesmo_username_nao_causa_conflito_entre_user_ids(self):
        for user_id in (10, 20):
            cadastros.atualizar_perfil_telegram(
                telegram_user_id=user_id,
                chat_id=user_id,
                username="nome_repetido",
                first_name="Pessoa",
                last_name=str(user_id),
                language_code="pt-br",
            )
        with sqlite3.connect(cadastros.DB_CADASTROS) as con:
            total = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        self.assertEqual(total, 2)

    def test_documento_aguarda_e_e_liberado_apos_cadastro(self):
        item_id = fila_bot.adicionar_na_fila(
            chat_id=100,
            user_id=123,
            file_id="arquivo",
            file_name="nota.pdf",
            local_pdf="nota.pdf",
            chave="1" * 50,
            origem_chave="TEXTO_PDF",
            tipo_documento="NFSE",
            status="AGUARDANDO_CADASTRO",
        )
        self.assertEqual(fila_bot.contar_pendentes_cadastro(123), 1)
        self.assertEqual(fila_bot.liberar_pendentes_cadastro(123), [item_id])
        self.assertEqual(fila_bot.obter_item(item_id)["status"], "AGUARDANDO")

    def test_historico_preserva_solicitante(self):
        historico.registrar(
            chave="2" * 50,
            tipo_documento="NFSE",
            nota="74",
            fornecedor="Prestador",
            destinatario="Empresa01",
            cnpj_destinatario="11111111111111",
            origem_chave="TEXTO_PDF",
            xml_origem="local.xml",
            xml_destino=r"C:\Destino\11111111111111\nota.xml",
            status="CONCLUIDO",
            telegram_user_id=123,
            telegram_chat_id=456,
            telegram_username="usuario",
            solicitante_nome="Nome Sobrenome",
            solicitante_setor="Setor",
        )
        registro = historico.buscar_por_chave("2" * 50)[0]
        self.assertEqual(registro["telegram_user_id"], 123)
        self.assertEqual(registro["solicitante_nome"], "Nome Sobrenome")
        self.assertEqual(registro["solicitante_setor"], "Setor")

    def test_formato_setor_nome(self):
        self.assertEqual(
            cadastros.interpretar_setor_nome("Qualidade + Maria da Silva"),
            ("Qualidade", "Maria da Silva"),
        )
        with self.assertRaises(ValueError):
            cadastros.interpretar_setor_nome("Qualidade Maria")

    def test_migracao_preserva_bancos_da_versao_anterior(self):
        pasta = Path(self.temp.name)
        fila_legada = pasta / "fila_legada.sqlite3"
        historico_legado = pasta / "historico_legado.sqlite3"

        with sqlite3.connect(fila_legada) as con:
            con.execute(
                """
                CREATE TABLE fila_importacao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    local_pdf TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'AGUARDANDO',
                    criado_em TEXT NOT NULL,
                    iniciado_em TEXT,
                    finalizado_em TEXT,
                    erro TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE usuarios_bot (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    primeiro_start_em TEXT NOT NULL
                )
                """
            )

        with sqlite3.connect(historico_legado) as con:
            con.execute(
                """
                CREATE TABLE processados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave TEXT NOT NULL,
                    nota TEXT,
                    fornecedor TEXT,
                    destinatario TEXT,
                    cnpj_destinatario TEXT,
                    origem_chave TEXT,
                    xml_origem TEXT,
                    xml_destino TEXT,
                    status TEXT NOT NULL,
                    criado_em TEXT NOT NULL
                )
                """
            )

        fila_bot.DB_FILA = fila_legada
        historico.DB = historico_legado
        fila_bot.inicializar_fila()
        historico.inicializar()

        with sqlite3.connect(fila_legada) as con:
            colunas_fila = {
                row[1] for row in con.execute("PRAGMA table_info(fila_importacao)")
            }
        with sqlite3.connect(historico_legado) as con:
            colunas_historico = {
                row[1] for row in con.execute("PRAGMA table_info(processados)")
            }

        self.assertTrue(
            {"chave", "origem_chave", "tipo_documento"} <= colunas_fila
        )
        self.assertTrue(
            {
                "tipo_documento",
                "telegram_user_id",
                "solicitante_nome",
                "solicitante_setor",
            }
            <= colunas_historico
        )


if __name__ == "__main__":
    unittest.main()
