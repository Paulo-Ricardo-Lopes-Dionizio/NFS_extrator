from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime

from app_config import BASE

DB_CADASTROS = BASE / "cadastros.sqlite3"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def inicializar_cadastros() -> None:
    with closing(sqlite3.connect(DB_CADASTROS)) as con, con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                telegram_user_id INTEGER PRIMARY KEY,
                username TEXT,
                telegram_first_name TEXT,
                telegram_last_name TEXT,
                language_code TEXT,
                ultimo_chat_id INTEGER,
                setor TEXT,
                nome_completo TEXT,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_usuarios_username "
            "ON usuarios(username)"
        )


def atualizar_perfil_telegram(
    *,
    telegram_user_id: int,
    chat_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None,
) -> None:
    agora = _agora()
    with closing(sqlite3.connect(DB_CADASTROS)) as con, con:
        con.execute(
            """
            INSERT INTO usuarios (
                telegram_user_id, username, telegram_first_name,
                telegram_last_name, language_code, ultimo_chat_id,
                criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username=excluded.username,
                telegram_first_name=excluded.telegram_first_name,
                telegram_last_name=excluded.telegram_last_name,
                language_code=excluded.language_code,
                ultimo_chat_id=excluded.ultimo_chat_id,
                atualizado_em=excluded.atualizado_em
            """,
            (
                telegram_user_id,
                (username or "").strip() or None,
                (first_name or "").strip() or None,
                (last_name or "").strip() or None,
                (language_code or "").strip() or None,
                chat_id,
                agora,
                agora,
            ),
        )


def obter_cadastro(telegram_user_id: int) -> dict | None:
    with closing(sqlite3.connect(DB_CADASTROS)) as con, con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM usuarios WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return dict(row) if row else None


def cadastro_completo(telegram_user_id: int) -> bool:
    cadastro = obter_cadastro(telegram_user_id)
    return bool(
        cadastro
        and (cadastro.get("setor") or "").strip()
        and (cadastro.get("nome_completo") or "").strip()
    )


def interpretar_setor_nome(texto: str) -> tuple[str, str]:
    texto = re.sub(r"\s+", " ", texto.strip())
    if texto.count("+") != 1:
        raise ValueError(
            "Use exatamente o formato: Setor + Nome completo"
        )

    setor, nome = (parte.strip() for parte in texto.split("+", 1))
    if len(setor) < 2:
        raise ValueError("Informe um setor válido antes do sinal +.")
    if len(nome.split()) < 2:
        raise ValueError("Informe nome e sobrenome depois do sinal +.")
    if len(setor) > 100 or len(nome) > 200:
        raise ValueError("Setor ou nome acima do tamanho permitido.")
    return setor, nome


def salvar_cadastro(
    telegram_user_id: int,
    setor: str,
    nome_completo: str,
) -> dict:
    setor, nome_completo = interpretar_setor_nome(
        f"{setor} + {nome_completo}"
    )
    agora = _agora()
    with closing(sqlite3.connect(DB_CADASTROS)) as con, con:
        existe = con.execute(
            "SELECT 1 FROM usuarios WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        if existe:
            con.execute(
                """
                UPDATE usuarios
                SET setor=?, nome_completo=?, atualizado_em=?
                WHERE telegram_user_id=?
                """,
                (setor, nome_completo, agora, telegram_user_id),
            )
        else:
            con.execute(
                """
                INSERT INTO usuarios (
                    telegram_user_id, setor, nome_completo,
                    criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_user_id, setor, nome_completo, agora, agora),
            )

    cadastro = obter_cadastro(telegram_user_id)
    if cadastro is None:
        raise RuntimeError("Cadastro não pôde ser salvo.")
    return cadastro
