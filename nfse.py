from __future__ import annotations

import base64
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

from requests_pkcs12 import get as pkcs12_get

from app_config import NFSE_CERT_PFX, NFSE_XML_DIR, NFE_CERT_SENHA

BASE_URL = "https://sefin.nfse.gov.br/sefinnacional"


def consultar_nfse(chave: str) -> tuple[str, str, Path | None]:
    destino = NFSE_XML_DIR / f"{chave}.xml"

    if destino.is_file():
        return "XML_COMPLETO", "XML já existente localmente.", destino

    if not NFSE_CERT_PFX.is_file():
        return (
            "ERRO_CERTIFICADO",
            f"Certificado não encontrado: {NFSE_CERT_PFX}",
            None,
        )

    url = f"{BASE_URL}/nfse/{chave}"

    try:
        response = pkcs12_get(
            url,
            pkcs12_filename=str(NFSE_CERT_PFX),
            pkcs12_password=NFE_CERT_SENHA,
            timeout=60,
        )
    except Exception as exc:
        return "ERRO_HTTP", str(exc), None

    if response.status_code != 200:
        return f"HTTP_{response.status_code}", response.text[:1000], None

    try:
        data = response.json()
    except Exception as exc:
        return "ERRO_JSON", str(exc), None

    conteudo_b64 = (
        data.get("nfseXmlGZipB64")
        or data.get("xmlGZipB64")
        or ""
    )

    if not conteudo_b64:
        return (
            "XML_NAO_ENCONTRADO",
            "Resposta não contém XML Base64.",
            None,
        )

    try:
        comprimido = base64.b64decode(conteudo_b64)
        xml_bytes = gzip.decompress(comprimido)
        destino.write_bytes(xml_bytes)
    except Exception as exc:
        return "ERRO_DECODIFICACAO", str(exc), None

    return "XML_COMPLETO", "XML obtido com sucesso.", destino


def _texto(elemento: ET.Element | None) -> str:
    if elemento is None:
        return ""
    return (elemento.text or "").strip()


def extrair_dados_nfse(xml_path: Path) -> dict[str, str]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    ns = {"n": "http://www.sped.fazenda.gov.br/nfse"}

    numero = _texto(root.find(".//n:nNFSe", ns))

    emit = root.find(".//n:emit", ns)
    prest = root.find(".//n:prest", ns)
    toma = root.find(".//n:toma", ns)

    prestador = ""
    cnpj_prestador = ""

    if emit is not None:
        prestador = _texto(emit.find("n:xNome", ns))
        cnpj_prestador = _texto(emit.find("n:CNPJ", ns))

    if prest is not None:
        if not prestador:
            prestador = _texto(prest.find("n:xNome", ns))
        if not cnpj_prestador:
            cnpj_prestador = _texto(prest.find("n:CNPJ", ns))

    tomador = ""
    documento_tomador = ""

    if toma is not None:
        tomador = _texto(toma.find("n:xNome", ns))
        documento_tomador = (
            _texto(toma.find("n:CNPJ", ns))
            or _texto(toma.find("n:CPF", ns))
        )

    return {
        "numero_nfse": numero,
        "prestador": prestador,
        "cnpj_prestador": cnpj_prestador,
        "tomador": tomador,
        "cnpj_tomador": documento_tomador,
    }
