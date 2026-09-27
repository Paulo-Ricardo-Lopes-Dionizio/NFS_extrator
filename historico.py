from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime

from app_config import BASE

DB = BASE / "processados.sqlite3"


def inicializar() -> None:
    with closing(sqlite3.connect(DB)) as con, con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS processados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL,
                tipo_documento TEXT,
                nota TEXT,
                fornecedor TEXT,
                destinatario TEXT,
                cnpj_destinatario TEXT,
                origem_chave TEXT,
                xml_origem TEXT,
                xml_destino TEXT,
                telegram_user_id INTEGER,
                telegram_chat_id INTEGER,
                telegram_username TEXT,
                solicitante_nome TEXT,
                solicitante_setor TEXT,
                status TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )
        colunas = {
            linha[1]
            for linha in con.execute("PRAGMA table_info(processados)").fetchall()
        }
        for nome, tipo_sql in (
            ("tipo_documento", "TEXT"),
            ("xml_destino", "TEXT"),
            ("telegram_user_id", "INTEGER"),
            ("telegram_chat_id", "INTEGER"),
            ("telegram_username", "TEXT"),
            ("solicitante_nome", "TEXT"),
            ("solicitante_setor", "TEXT"),
        ):
            if nome not in colunas:
                con.execute(f"ALTER TABLE processados ADD COLUMN {nome} {tipo_sql}")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_processados_chave ON processados(chave)"
        )


def registrar(
    *,
    chave: str,
    tipo_documento: str | None,
    nota: str | None,
    fornecedor: str | None,
    destinatario: str | None,
    cnpj_destinatario: str | None,
    origem_chave: str | None,
    xml_origem: str | None,
    xml_destino: str | None,
    status: str,
    telegram_user_id: int | None = None,
    telegram_chat_id: int | None = None,
    telegram_username: str | None = None,
    solicitante_nome: str | None = None,
    solicitante_setor: str | None = None,
) -> None:
    with closing(sqlite3.connect(DB)) as con, con:
        con.execute(
            """
            INSERT INTO processados (
                chave, tipo_documento, nota, fornecedor, destinatario,
                cnpj_destinatario, origem_chave,
                xml_origem, xml_destino, telegram_user_id,
                telegram_chat_id, telegram_username,
                solicitante_nome, solicitante_setor,
                status, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chave,
                tipo_documento,
                nota,
                fornecedor,
                destinatario,
                cnpj_destinatario,
                origem_chave,
                xml_origem,
                xml_destino,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                solicitante_nome,
                solicitante_setor,
                status,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def ultimo_sucesso(chave: str) -> dict | None:
    with closing(sqlite3.connect(DB)) as con, con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            SELECT *
            FROM processados
            WHERE chave = ? AND status = 'CONCLUIDO'
            ORDER BY id DESC
            LIMIT 1
            """,
            (chave,),
        ).fetchone()
        return dict(row) if row else None


def buscar_por_chave(chave: str, limite: int = 10) -> list[dict]:
    with closing(sqlite3.connect(DB)) as con, con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT *
            FROM processados
            WHERE chave = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chave, max(1, min(limite, 50))),
        ).fetchall()
        return [dict(row) for row in rows]
