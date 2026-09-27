from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from app_config import (
    NFE_CNPJS_EMITENTES_PROPRIOS,
    NFE_SCRIPT_EMITIDA,
    NFE_SCRIPT_RECEBIDA,
    NFE_TIMEOUT,
    NFE_XML_DIR,
    PHP_EXE,
)
from extrator_chave import chave_nfe_valida


def extrair_cnpj_emitente_da_chave(chave: str) -> str:
    return chave[6:20] if chave_nfe_valida(chave) else ""


def eh_emitente_proprio(cnpj: str) -> bool:
    return cnpj in NFE_CNPJS_EMITENTES_PROPRIOS


def _status_saida(saida: str, retorno: int) -> str:
    padroes = (
        "XML_COMPLETO",
        "RESUMO_ENCONTRADO",
        "NENHUM_XML_EXTRAIDO",
        "CONSUMO_INDEVIDO",
        "MANIFESTACAO_REJEITADA",
        "NFE_NAO_LOCALIZADA_DISTRIBUICAO",
        "DOCUMENTOS_SALVOS",
        "ERRO",
    )
    for status in padroes:
        if re.search(rf"(?:RESULTADO|STATUS)\s*=\s*{status}\b", saida, re.I):
            return status
    return "ERRO_PHP" if retorno else "STATUS_DESCONHECIDO"


def _xmls_informados_na_saida(saida: str) -> list[Path]:
    caminhos: list[Path] = []
    for correspondencia in re.finditer(
        r"(?im)^\s*(?:Documento|XML)\s+salvo\s*:\s*(.+?\.xml)\s*$",
        saida,
    ):
        bruto = correspondencia.group(1).strip().strip("\"'")
        if bruto:
            caminhos.append(Path(bruto))
    return caminhos


def _arquivo_corresponde_chave(arquivo: Path, chave: str) -> bool:
    if not arquivo.is_file():
        return False
    if chave in arquivo.name:
        return True
    try:
        return chave.encode("ascii") in arquivo.read_bytes()
    except OSError:
        return False


def _localizar_xml(chave: str, saida_php: str = "") -> Path | None:
    # Alguns scripts PHP mantêm uma pasta própria. Quando eles informam
    # "Documento salvo: ...", esse caminho é a fonte mais confiável.
    for arquivo in _xmls_informados_na_saida(saida_php):
        if _arquivo_corresponde_chave(arquivo, chave):
            return arquivo

    direto = NFE_XML_DIR / f"{chave}.xml"
    if _arquivo_corresponde_chave(direto, chave):
        return direto

    for arquivo in NFE_XML_DIR.glob("*.xml"):
        if _arquivo_corresponde_chave(arquivo, chave):
            return arquivo
    return None


def consultar_nfe(chave: str) -> tuple[str, str, Path | None]:
    if not chave_nfe_valida(chave):
        return "CHAVE_NFE_INVALIDA", "Chave NF-e inválida.", None

    existente = _localizar_xml(chave)
    if existente:
        return "XML_COMPLETO", "XML NF-e já existente localmente.", existente

    emitente = extrair_cnpj_emitente_da_chave(chave)
    emitida_por_empresa_propria = eh_emitente_proprio(emitente)
    script = (
        NFE_SCRIPT_EMITIDA
        if emitida_por_empresa_propria
        else NFE_SCRIPT_RECEBIDA
    )

    if not PHP_EXE.is_file():
        return "ERRO_PHP_NAO_ENCONTRADO", f"PHP não encontrado: {PHP_EXE}", None
    if not script.is_file():
        fluxo = (
            "NF-e emitida por empresa própria"
            if emitida_por_empresa_propria
            else "NF-e recebida de fornecedor"
        )
        variavel = (
            "NFE_SCRIPT_EMITIDA"
            if emitida_por_empresa_propria
            else "NFE_SCRIPT_RECEBIDA"
        )
        return (
            "ERRO_SCRIPT_NFE",
            (
                f"{fluxo}. Script SEFAZ não encontrado: {script}. "
                f"Corrija {variavel} no arquivo .env ou copie o PHP para esse "
                "caminho. empresas_certificadas.json controla somente as "
                "pastas de destino e não substitui o script de obtenção do XML."
            ),
            None,
        )

    ambiente = os.environ.copy()
    ambiente["NFE_XML_DIR"] = str(NFE_XML_DIR)

    try:
        processo = subprocess.run(
            [str(PHP_EXE), str(script), chave],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=NFE_TIMEOUT,
            env=ambiente,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "ERRO_TIMEOUT_NFE", f"Consulta excedeu {NFE_TIMEOUT} segundos.", None
    except OSError as exc:
        return "ERRO_EXECUCAO_NFE", str(exc), None

    saida = "\n".join(
        parte.strip() for parte in (processo.stdout, processo.stderr) if parte.strip()
    )
    status = _status_saida(saida, processo.returncode)
    xml = _localizar_xml(chave, saida)

    if xml:
        return "XML_COMPLETO", saida[-3000:] or "XML obtido com sucesso.", xml

    detalhe_fluxo = (
        "NF-e emitida por empresa própria; usado o certificado alternativo configurado."
        if emitida_por_empresa_propria
        else "NF-e recebida; usado fluxo de Distribuição DF-e/manifestação."
    )
    detalhe = f"{detalhe_fluxo}\n{saida[-3000:]}".strip()
    if status == "XML_COMPLETO":
        status = "XML_COMPLETO_SEM_ARQUIVO"
        detalhe += (
            "\nO PHP informou sucesso, mas o arquivo não foi encontrado no "
            "caminho exibido nem em NFE_XML_DIR. Confira a linha "
            "'Documento salvo:' e a configuração NFE_XML_DIR do .env."
        )
    return status, detalhe, None
