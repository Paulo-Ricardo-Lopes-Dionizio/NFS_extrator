from __future__ import annotations

import shutil
from pathlib import Path

from app_config import CRIAR_SUBPASTA_DOCUMENTO, DESTINO_NFE, DESTINO_NFSE
from roteamento import normalizar_documento


def base_destino(tipo_documento: str) -> Path:
    """Retorna a raiz configurada para o tipo fiscal."""
    return DESTINO_NFSE if tipo_documento.upper() == "NFSE" else DESTINO_NFE


def montar_destino_local(
    xml_local: Path,
    documento: str,
    tipo_documento: str,
) -> Path:
    documento = normalizar_documento(documento)
    base = base_destino(tipo_documento)
    pasta = base / documento if CRIAR_SUBPASTA_DOCUMENTO else base
    return pasta / Path(xml_local).name


def salvar_xml(
    xml_local: Path,
    documento: str,
    tipo_documento: str,
) -> dict[str, str]:
    """Copia o XML para a pasta escolhida no .env, sem automação de interface."""
    xml_local = Path(xml_local)
    if not xml_local.is_file():
        raise FileNotFoundError(xml_local)

    destino = montar_destino_local(xml_local, documento, tipo_documento)
    destino.parent.mkdir(parents=True, exist_ok=True)

    # copy2 preserva metadados básicos e funciona também com compartilhamentos UNC.
    shutil.copy2(xml_local, destino)

    if not destino.is_file():
        raise RuntimeError(f"Não foi possível criar o XML em: {destino}")

    return {
        "status": "XML_SALVO",
        "arquivo_destino": str(destino),
        "tipo_documento": tipo_documento,
    }
