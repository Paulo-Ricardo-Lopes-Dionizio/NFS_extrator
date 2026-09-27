from __future__ import annotations

import json
import re
from pathlib import Path

from app_config import EMPRESAS_CERTIFICADAS_ARQUIVO, EXIGIR_CNPJ_CADASTRADO


def normalizar_documento(documento: str) -> str:
    limpo = re.sub(r"\D", "", documento or "")
    if len(limpo) not in (11, 14):
        raise ValueError(f"CNPJ/CPF do destinatário inválido: {documento!r}")
    return limpo


def carregar_empresas() -> dict[str, str]:
    caminho = Path(EMPRESAS_CERTIFICADAS_ARQUIVO)
    if not caminho.is_file():
        return {}
    texto = caminho.read_text(encoding="utf-8-sig").replace("\u00a0", " ")
    dados = json.loads(texto)
    if not isinstance(dados, list):
        raise ValueError("empresas_certificadas.json deve conter uma lista JSON.")
    empresas: dict[str, str] = {}
    for item in dados:
        if not isinstance(item, dict):
            continue
        cnpj = re.sub(r"\D", "", str(item.get("cnpj", "")))
        if len(cnpj) == 14:
            empresas[cnpj] = str(item.get("nome", "")).strip() or cnpj
    return empresas


def validar_destinatario(documento: str) -> tuple[str, str]:
    documento = normalizar_documento(documento)
    empresas = carregar_empresas()
    nome = empresas.get(documento, "")
    if EXIGIR_CNPJ_CADASTRADO and not nome:
        raise ValueError(
            "CNPJ do destinatário não cadastrado em empresas_certificadas.json: "
            f"{documento}"
        )
    return documento, nome or "Documento válido"
