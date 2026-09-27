from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texto(elemento: ET.Element | None) -> str:
    return (elemento.text or "").strip() if elemento is not None else ""


def _filho(elemento: ET.Element | None, *nomes: str) -> ET.Element | None:
    if elemento is None:
        return None
    procurados = set(nomes)
    for filho in elemento.iter():
        if _local(filho.tag) in procurados:
            return filho
    return None


def _primeiro(root: ET.Element, *nomes: str) -> ET.Element | None:
    procurados = set(nomes)
    for elemento in root.iter():
        if _local(elemento.tag) in procurados:
            return elemento
    return None


def _documento(bloco: ET.Element | None) -> str:
    valor = _texto(_filho(bloco, "CNPJ")) or _texto(_filho(bloco, "CPF"))
    return re.sub(r"\D", "", valor)


def detectar_tipo_xml(root: ET.Element) -> str:
    tags = {_local(elemento.tag) for elemento in root.iter()}
    if {"NFe", "nfeProc"} & tags or {"ide", "emit", "dest"}.issubset(tags):
        return "NFE"
    if {"NFSe", "DPS", "infNFSe"} & tags or "toma" in tags:
        return "NFSE"
    return "DESCONHECIDO"


def extrair_dados_xml(xml_path: Path, tipo_esperado: str = "") -> dict[str, str]:
    root = ET.parse(xml_path).getroot()
    tipo_detectado = detectar_tipo_xml(root)
    tipo = tipo_detectado if tipo_detectado != "DESCONHECIDO" else tipo_esperado

    if tipo == "NFE":
        ide = _primeiro(root, "ide")
        emit = _primeiro(root, "emit")
        dest = _primeiro(root, "dest")
        return {
            "tipo": "NFE",
            "numero": _texto(_filho(ide, "nNF")),
            "emitente": _texto(_filho(emit, "xNome")),
            "cnpj_emitente": _documento(emit),
            "destinatario": _texto(_filho(dest, "xNome")),
            "cnpj_destinatario": _documento(dest),
        }

    emit = _primeiro(root, "emit")
    prest = _primeiro(root, "prest")
    toma = _primeiro(root, "toma", "tomador", "Toma")
    prestador = _texto(_filho(emit, "xNome")) or _texto(_filho(prest, "xNome"))
    cnpj_prestador = _documento(emit) or _documento(prest)

    return {
        "tipo": "NFSE" if tipo == "NFSE" else tipo,
        "numero": _texto(_primeiro(root, "nNFSe", "nNFS", "Numero")),
        "emitente": prestador,
        "cnpj_emitente": cnpj_prestador,
        "destinatario": _texto(_filho(toma, "xNome", "RazaoSocial")),
        "cnpj_destinatario": _documento(toma),
    }
