from __future__ import annotations

import io
import re
from pathlib import Path

import pymupdf

from app_config import OCR_DEBUG_DIR, TESSERACT_EXE

CHAVE_CONTIGUA = re.compile(r"(?<!\d)(\d{44}|\d{50})(?!\d)")
CHAVE_AGRUPADA = re.compile(
    r"(?<!\d)((?:\d{2,4}[\s.\-/]+){9,16}\d{2,4})(?!\d)"
)
MARCADORES = (
    "CHAVE DE ACESSO",
    "CHAVE DA NF-E",
    "CHAVE DA NFS-E",
    "CHAVE NFS-E",
    "CHAVE NF-E",
)


def calcular_dv_nfe(base: str) -> int:
    peso = 2
    soma = 0
    for caractere in reversed(base):
        soma += int(caractere) * peso
        peso += 1
        if peso > 9:
            peso = 2
    dv = 11 - (soma % 11)
    return 0 if dv in (10, 11) else dv


def chave_nfe_valida(chave: str) -> bool:
    return (
        bool(re.fullmatch(r"\d{44}", chave))
        and calcular_dv_nfe(chave[:43]) == int(chave[43])
    )


def _candidatos(trecho: str) -> list[str]:
    encontrados: list[str] = []

    for match in CHAVE_CONTIGUA.finditer(trecho):
        encontrados.append(match.group(1))

    for match in CHAVE_AGRUPADA.finditer(trecho):
        digitos = re.sub(r"\D", "", match.group(1))
        if len(digitos) in (44, 50):
            encontrados.append(digitos)

    # O OCR pode separar a chave em linhas. Analisa janelas curtas, sem
    # concatenar indiscriminadamente todos os números do documento.
    linhas = trecho.splitlines()
    for indice in range(len(linhas)):
        janela = " ".join(linhas[indice:indice + 3])
        digitos = re.sub(r"\D", "", janela)
        if len(digitos) in (44, 50):
            encontrados.append(digitos)

    return list(dict.fromkeys(encontrados))


def localizar_chave(texto: str) -> tuple[str | None, str]:
    texto_normalizado = texto.replace("\u00a0", " ")
    texto_maiusculo = texto_normalizado.upper()

    trechos_prioritarios: list[str] = []
    for marcador in MARCADORES:
        inicio = 0
        while True:
            posicao = texto_maiusculo.find(marcador, inicio)
            if posicao < 0:
                break
            trechos_prioritarios.append(
                texto_normalizado[max(0, posicao - 100):posicao + 700]
            )
            inicio = posicao + len(marcador)

    # Primeiro tenta perto do rótulo; depois, no texto completo.
    for trecho in (*trechos_prioritarios, texto_normalizado):
        candidatos = _candidatos(trecho)

        # Uma chave NF-e só é aceita com o dígito verificador correto.
        for chave in candidatos:
            if len(chave) == 44 and chave_nfe_valida(chave):
                return chave, "NFE"

        # A NFS-e Nacional usa chave de 50 dígitos. No texto completo ela não
        # é aceita sem o rótulo, reduzindo falsos positivos.
        for chave in candidatos:
            if len(chave) == 50 and trecho in trechos_prioritarios:
                return chave, "NFSE"

    return None, "DESCONHECIDO"


def extrair_texto_pdf(pdf: Path) -> str:
    partes: list[str] = []

    try:
        with pymupdf.open(pdf) as documento:
            partes.extend(pagina.get_text("text") for pagina in documento)
    except Exception:
        pass

    texto = "\n".join(partes).strip()
    if texto:
        return texto

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf))
        return "\n".join((pagina.extract_text() or "") for pagina in reader.pages)
    except Exception:
        return ""


def _imagem_pagina(pdf: Path):
    from PIL import Image

    with pymupdf.open(pdf) as documento:
        if documento.page_count == 0:
            raise ValueError("PDF sem páginas.")
        pagina = documento[0]
        pixmap = pagina.get_pixmap(matrix=pymupdf.Matrix(4, 4), alpha=False)
        return Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")


def _preparar_ocr(imagem):
    from PIL import ImageFilter, ImageOps

    largura, altura = imagem.size
    regioes = {
        "topo_completo": imagem.crop((0, 0, largura, int(altura * 0.45))),
        "topo_direito": imagem.crop(
            (int(largura * 0.42), 0, largura, int(altura * 0.45))
        ),
        "chave_direita": imagem.crop(
            (int(largura * 0.53), int(altura * 0.08), largura, int(altura * 0.30))
        ),
        "pagina_inteira": imagem,
    }

    resultados: list[tuple[str, object]] = []
    for nome, regiao in regioes.items():
        cinza = ImageOps.autocontrast(ImageOps.grayscale(regiao))
        nitida = cinza.filter(ImageFilter.SHARPEN)
        resultados.append((nome, nitida))
        resultados.append((f"{nome}_bin", nitida.point(lambda p: 255 if p > 165 else 0)))
    return resultados


def _ocr_pdf(pdf: Path) -> tuple[str | None, str]:
    try:
        import pytesseract
    except ImportError:
        return None, "DESCONHECIDO"

    if TESSERACT_EXE.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)

    imagem = _imagem_pagina(pdf)
    OCR_DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    for nome, regiao in _preparar_ocr(imagem):
        try:
            regiao.save(OCR_DEBUG_DIR / f"{pdf.stem}_{nome}.png")
            texto = pytesseract.image_to_string(
                regiao,
                lang="por",
                config="--psm 6",
            )
            chave, tipo = localizar_chave(texto)
            if chave:
                return chave, tipo

            texto_numerico = pytesseract.image_to_string(
                regiao,
                config=(
                    "--psm 6 "
                    "-c tessedit_char_whitelist=0123456789.-/ "
                ),
            )
            chave, tipo = localizar_chave("CHAVE DE ACESSO\n" + texto_numerico)
            if chave:
                return chave, tipo
        except Exception:
            continue

    return None, "DESCONHECIDO"


def obter_chave(pdf: Path) -> tuple[str | None, str, str]:
    pdf = Path(pdf)

    texto = extrair_texto_pdf(pdf)
    chave, tipo = localizar_chave(texto)
    if chave:
        return chave, "TEXTO_PDF", tipo

    chave, tipo = _ocr_pdf(pdf)
    if chave:
        return chave, "OCR_TESSERACT", tipo

    return None, "NAO_ENCONTRADA", "DESCONHECIDO"


def extrair_cnpj_destinatario_pdf(pdf: Path) -> str:
    """Fallback controlado; o XML continua sendo a fonte principal."""
    texto = extrair_texto_pdf(Path(pdf))
    texto_maiusculo = texto.upper()

    # Em muitos DANFEs, a ordem interna do texto põe o bloco do destinatário
    # antes do título visual "DESTINATÁRIO / REMETENTE".
    rotulo_cnpj = re.search(
        r"CNPJ\s*/\s*CPF\s*[:\n ]+"
        r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})",
        texto,
        re.I,
    )
    if rotulo_cnpj:
        return re.sub(r"\D", "", rotulo_cnpj.group(1))

    for marcador in (
        "DESTINATÁRIO / REMETENTE",
        "DESTINATARIO / REMETENTE",
        "TOMADOR",
    ):
        posicao = texto_maiusculo.find(marcador)
        if posicao < 0:
            continue
        trecho = texto[max(0, posicao - 1800):posicao + 1800]
        match = re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", trecho)
        if match:
            return re.sub(r"\D", "", match.group(0))
    return ""
