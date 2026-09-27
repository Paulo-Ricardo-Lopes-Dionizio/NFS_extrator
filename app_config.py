from __future__ import annotations

import os
import re
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Permite testar módulos puros antes de instalar a .venv.
    def load_dotenv(*_args, **_kwargs):
        return False

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env", override=True)


def _inteiro(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, str(padrao)).strip())
    except (TypeError, ValueError):
        return padrao


def _booleano(nome: str, padrao: bool) -> bool:
    valor_padrao = "1" if padrao else "0"
    return os.getenv(nome, valor_padrao).strip().lower() not in {
        "0", "false", "nao", "não", "off",
    }


def _cnpj_env(nome: str, padrao: str = "") -> str:
    return re.sub(r"\D", "", os.getenv(nome, padrao))


def _cnpjs_env(nome: str, padrao: str = "") -> set[str]:
    return {
        cnpj
        for item in os.getenv(nome, padrao).split(",")
        if len(cnpj := re.sub(r"\D", "", item)) == 14
    }


def _caminho_env(nome: str, padrao: Path | str) -> Path:
    bruto = os.getenv(nome, str(padrao)).strip()
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else BASE / caminho


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS = {
    int(item.strip())
    for item in raw_ids.split(",")
    if item.strip()
} if raw_ids else set()

raw_admin_ids = os.getenv("TELEGRAM_ADMIN_USER_IDS", "").strip()
ADMIN_USER_IDS = {
    int(item.strip())
    for item in raw_admin_ids.split(",")
    if item.strip()
} if raw_admin_ids else set()

DANFE_DIR = BASE / "danfe"
PROCESSADOS_DIR = DANFE_DIR / "processados"
XML_DIR = BASE / "xml"
NFSE_XML_DIR = XML_DIR / "nfse_completos"
NFE_XML_DIR = _caminho_env("NFE_XML_DIR", XML_DIR / "completos")
LOG_DIR = BASE / "logs"
OCR_DEBUG_DIR = LOG_DIR / "ocr_debug"
CERT_DIR = BASE / "certificado"
EXEMPLOS_DIR = BASE / "exemplos"

# Pastas de saída finais. Podem ser locais, outra unidade ou compartilhamentos UNC.
DESTINO_NFE = _caminho_env("DESTINO_NFE", BASE / "saida" / "NFE")
DESTINO_NFSE = _caminho_env("DESTINO_NFSE", BASE / "saida" / "NFSE")
CRIAR_SUBPASTA_DOCUMENTO = _booleano("CRIAR_SUBPASTA_DOCUMENTO", True)

for pasta in (
    DANFE_DIR,
    PROCESSADOS_DIR,
    XML_DIR,
    NFSE_XML_DIR,
    NFE_XML_DIR,
    LOG_DIR,
    OCR_DEBUG_DIR,
    CERT_DIR,
    EXEMPLOS_DIR,
):
    pasta.mkdir(parents=True, exist_ok=True)

# NFS-e Nacional
NFSE_CERT_PFX = _caminho_env("NFSE_CERT_PFX", CERT_DIR / "empresa.pfx")
NFE_CERT_SENHA = os.getenv("NFE_CERT_SENHA", "").strip()

# NF-e modelo 55. O bot utiliza os scripts PHP incluídos no projeto.
PHP_EXE = _caminho_env("PHP_EXE", r"C:\php\php.exe")
NFE_SCRIPT_RECEBIDA = _caminho_env(
    "NFE_SCRIPT_RECEBIDA",
    BASE / "baixar_por_chave_com_manifestacao.php",
)
NFE_SCRIPT_EMITIDA = _caminho_env(
    "NFE_SCRIPT_EMITIDA",
    BASE / "baixar_emitida.php",
)
EMPRESA_CNPJ = _cnpj_env("EMPRESA_CNPJ")
NFE_CNPJS_EMITENTES_PROPRIOS = _cnpjs_env(
    "NFE_CNPJS_EMITENTES_PROPRIOS",
    EMPRESA_CNPJ,
)
NFE_TIMEOUT = _inteiro("NFE_TIMEOUT", 180)

# OCR
TESSERACT_EXE = _caminho_env(
    "TESSERACT_EXE",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

# Validação opcional de destinatários autorizados.
EMPRESAS_CERTIFICADAS_ARQUIVO = _caminho_env(
    "EMPRESAS_CERTIFICADAS_ARQUIVO",
    BASE / "empresas_certificadas.json",
)
EXIGIR_CNPJ_CADASTRADO = _booleano("EXIGIR_CNPJ_CADASTRADO", False)
