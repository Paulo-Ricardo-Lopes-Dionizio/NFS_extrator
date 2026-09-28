from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Permite testar módulos puros antes de instalar a .venv.
    def load_dotenv(*_args, **_kwargs):
        return False

# BASE continua sendo a pasta dos recursos do programa, para compatibilidade.
BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
APP_DIR = BASE
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local/share")) / "NFS Extrator"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = DATA_DIR / ".env"
# Em desenvolvimento permite o .env da raiz somente se nao existe configuracao local.
if ENV_FILE.is_file():
    load_dotenv(ENV_FILE, override=True)
elif not getattr(sys, "frozen", False):
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
    bruto = os.getenv(nome, "").strip() or str(padrao)
    bruto = os.path.expandvars(os.path.expanduser(bruto))
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

DANFE_DIR = DATA_DIR / "danfe"
PROCESSADOS_DIR = DANFE_DIR / "processados"
XML_DIR = DATA_DIR / "xml"
NFSE_XML_DIR = XML_DIR / "nfse_completos"
NFE_XML_DIR = _caminho_env("NFE_XML_DIR", XML_DIR / "completos")
LOG_DIR = DATA_DIR / "logs"
OCR_DEBUG_DIR = LOG_DIR / "ocr_debug"
CERT_DIR = DATA_DIR / "certificado"
EXEMPLOS_DIR = BASE / "exemplos"

# Pastas de saída finais. Podem ser locais, outra unidade ou compartilhamentos UNC.
DESTINO_NFE = _caminho_env("DESTINO_NFE", DATA_DIR / "saida" / "NFE")
DESTINO_NFSE = _caminho_env("DESTINO_NFSE", DATA_DIR / "saida" / "NFSE")
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
):
    pasta.mkdir(parents=True, exist_ok=True)

# NFS-e Nacional
NFSE_CERT_PFX = _caminho_env("NFSE_CERT_PFX", CERT_DIR / "empresa.pfx")
NFE_CERT_SENHA = os.getenv("NFE_CERT_SENHA", "")

# NF-e modelo 55. O bot utiliza os scripts PHP incluídos no projeto.
PHP_EXE = _caminho_env("PHP_EXE", BASE / "runtime" / "php" / "php.exe")
# Variaveis apenas deste processo, herdadas por subprocessos PHP.
# Nenhuma alteracao de PATH ou de variaveis globais do Windows.
if PHP_EXE.resolve() == (BASE / "runtime" / "php" / "php.exe").resolve():
    os.environ["NFS_PHP_DIR"] = str(PHP_EXE.parent)
    os.environ["NFS_PHP_CA_FILE"] = str(PHP_EXE.parent / "cacert.pem")
    os.environ["PHPRC"] = str(PHP_EXE.parent / "php.ini")
    scan_dir = DATA_DIR / "php_ini_scan_vazio"
    scan_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PHP_INI_SCAN_DIR"] = str(scan_dir)

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

# OCR: prioriza runtime privado; depois PATH; depois locais usuais do Windows.
import shutil

def _tesseract_padrao() -> Path:
    candidatos = [BASE / "runtime" / "tesseract" / "tesseract.exe"]
    achado = shutil.which("tesseract")
    if achado:
        candidatos.append(Path(achado))
    for nome in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        if os.getenv(nome):
            candidatos.append(Path(os.environ[nome]) / "Tesseract-OCR" / "tesseract.exe")
    candidatos.append(DATA_DIR.parent / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return next((p for p in candidatos if p.is_file()), candidatos[0])

TESSERACT_EXE = _caminho_env(
    "TESSERACT_EXE",
    _tesseract_padrao(),
)

# Validação opcional de destinatários autorizados.
EMPRESAS_CERTIFICADAS_ARQUIVO = _caminho_env(
    "EMPRESAS_CERTIFICADAS_ARQUIVO",
    BASE / "empresas_certificadas.json",
)
EXIGIR_CNPJ_CADASTRADO = _booleano("EXIGIR_CNPJ_CADASTRADO", False)

