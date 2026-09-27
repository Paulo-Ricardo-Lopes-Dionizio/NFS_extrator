from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from app_config import BASE

DB_FILA = BASE / "fila_bot.sqlite3"


def inicializar_fila() -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS fila_importacao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                local_pdf TEXT NOT NULL,
                chave TEXT,
                origem_chave TEXT,
                tipo_documento TEXT,
                status TEXT NOT NULL DEFAULT 'AGUARDANDO',
                criado_em TEXT NOT NULL,
                iniciado_em TEXT,
                finalizado_em TEXT,
                erro TEXT
            )
            """
        )
        colunas = {
            linha[1]
            for linha in con.execute("PRAGMA table_info(fila_importacao)").fetchall()
        }
        for nome, tipo_sql in (
            ("chave", "TEXT"),
            ("origem_chave", "TEXT"),
            ("tipo_documento", "TEXT"),
        ):
            if nome not in colunas:
                con.execute(
                    f"ALTER TABLE fila_importacao ADD COLUMN {nome} {tipo_sql}"
                )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios_bot (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                primeiro_start_em TEXT NOT NULL
            )
            """
        )


def usuario_ja_viu_intro(user_id: int) -> bool:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        row = con.execute(
            "SELECT 1 FROM usuarios_bot WHERE user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        return row is not None


def registrar_intro(user_id: int, chat_id: int) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            INSERT OR IGNORE INTO usuarios_bot (
                user_id, chat_id, primeiro_start_em
            ) VALUES (?, ?, ?)
            """,
            (
                user_id,
                chat_id,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def adicionar_na_fila(
    *,
    chat_id: int,
    user_id: int,
    file_id: str,
    file_name: str,
    local_pdf: str,
    chave: str | None = None,
    origem_chave: str | None = None,
    tipo_documento: str | None = None,
    status: str = "AGUARDANDO",
) -> int:
    if status not in {"AGUARDANDO", "AGUARDANDO_CADASTRO"}:
        raise ValueError(f"Status inicial inválido: {status}")
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        cur = con.execute(
            """
            INSERT INTO fila_importacao (
                chat_id, user_id, file_id, file_name,
                local_pdf, chave, origem_chave, tipo_documento,
                status, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                file_id,
                file_name,
                local_pdf,
                chave,
                origem_chave,
                tipo_documento,
                status,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)


def liberar_pendentes_cadastro(user_id: int) -> list[int]:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        rows = con.execute(
            """
            SELECT id FROM fila_importacao
            WHERE user_id=? AND status='AGUARDANDO_CADASTRO'
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()
        ids = [int(row[0]) for row in rows]
        if ids:
            marcadores = ",".join("?" for _ in ids)
            con.execute(
                f"""
                UPDATE fila_importacao
                SET status='AGUARDANDO', erro=NULL
                WHERE id IN ({marcadores})
                """,
                ids,
            )
        return ids


def contar_pendentes_cadastro(user_id: int) -> int:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        return int(
            con.execute(
                """
                SELECT COUNT(*) FROM fila_importacao
                WHERE user_id=? AND status='AGUARDANDO_CADASTRO'
                """,
                (user_id,),
            ).fetchone()[0]
        )


def obter_item(item_id: int) -> dict | None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM fila_importacao WHERE id = ?",
            (item_id,),
        ).fetchone()
        return dict(row) if row else None


def contar_aguardando() -> int:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        return int(
            con.execute(
                "SELECT COUNT(*) FROM fila_importacao WHERE status = 'AGUARDANDO'"
            ).fetchone()[0]
        )


def listar_pendentes() -> list[dict]:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT * FROM fila_importacao
            WHERE status IN ('AGUARDANDO', 'PROCESSANDO')
            ORDER BY id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def marcar_aguardando(item_id: int) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            UPDATE fila_importacao
            SET status='AGUARDANDO', iniciado_em=NULL,
                finalizado_em=NULL, erro=NULL
            WHERE id=?
            """,
            (item_id,),
        )


def marcar_aguardando_cadastro(item_id: int) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            UPDATE fila_importacao
            SET status='AGUARDANDO_CADASTRO', iniciado_em=NULL,
                finalizado_em=NULL, erro=NULL
            WHERE id=?
            """,
            (item_id,),
        )


def marcar_processando(item_id: int) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            UPDATE fila_importacao
            SET status='PROCESSANDO', iniciado_em=?
            WHERE id=?
            """,
            (datetime.now().isoformat(timespec="seconds"), item_id),
        )


def marcar_concluido(item_id: int) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            UPDATE fila_importacao
            SET status='CONCLUIDO', finalizado_em=?, erro=NULL
            WHERE id=?
            """,
            (datetime.now().isoformat(timespec="seconds"), item_id),
        )


def marcar_erro(item_id: int, erro: str) -> None:
    with closing(sqlite3.connect(DB_FILA)) as con, con:
        con.execute(
            """
            UPDATE fila_importacao
            SET status='ERRO', finalizado_em=?, erro=?
            WHERE id=?
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                erro[:4000],
                item_id,
            ),
        )
