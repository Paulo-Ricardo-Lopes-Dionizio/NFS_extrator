"""Execute na raiz do projeto DEPOIS do build PyInstaller. Python 3.10+.
Nao executa o bot, nao le .env nem copia certificados de cliente.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import ssl
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist' / 'NFS_Extrator'

def configurar_ini_portatil(path: Path):
    """Remove diretivas ativas antigas/duplicadas e grava as tres gerenciadas."""
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    text = re.sub(r'^\s*(?:extension_dir|curl\.cainfo|openssl\.cafile)\s*=.*$',
                  '', text, flags=re.MULTILINE | re.IGNORECASE)
    # As secoes anteriores sao preservadas; estas diretivas ficam por ultimo.
    text = text.rstrip() + '\n\n; Caminhos gerenciados pelo NFS Extrator\n'
    text += '[PHP]\nextension_dir = "${NFS_PHP_DIR}/ext"\n'
    text += '[curl]\ncurl.cainfo = "${NFS_PHP_CA_FILE}"\n'
    text += '[openssl]\nopenssl.cafile = "${NFS_PHP_CA_FILE}"\n'
    backup = path.with_name('php.ini.antes_preparacao.bak')
    if not backup.exists():
        backup.write_bytes(raw)
    path.write_text(text, encoding='utf-8', newline='\n')

def main():
    php_dir = ROOT / 'runtime/php'
    required = [DIST / 'NFS_Extrator.exe', php_dir / 'php.exe', php_dir / 'php.ini',
                ROOT / 'vendor/autoload.php', ROOT / 'baixar_emitida.php',
                ROOT / 'baixar_por_chave_com_manifestacao.php', ROOT / 'config.php',
                ROOT / 'installer_support/check_php.php']
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError('Arquivos ausentes:\n' + '\n'.join(missing))
    if not (ROOT / 'composer.lock').is_file():
        print('AVISO: composer.lock ausente; dependencias exatas ainda nao foram documentadas.')
    ca = php_dir / 'cacert.pem'
    if not ca.is_file():
        print('Baixando CA bundle publico via HTTPS de curl.se ...')
        with urllib.request.urlopen('https://curl.se/ca/cacert.pem', timeout=60) as response:
            contents = response.read(4 * 1024 * 1024)
        if b'-----BEGIN CERTIFICATE-----' not in contents:
            raise RuntimeError('Resposta recebida nao e um CA bundle PEM.')
        ca.write_bytes(contents)
    # Valida tambem um arquivo ja existente: existir nao significa ser PEM valido.
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(ca))
    except (OSError, ssl.SSLError) as exc:
        raise RuntimeError(f'CA bundle invalido ou ilegivel: {ca}. '
                           'Renomeie esse arquivo e execute novamente para baixar uma copia nova.') from exc
    configurar_ini_portatil(php_dir / 'php.ini')
    print('PHP:', php_dir / 'php.exe', flush=True)
    print('INI:', php_dir / 'php.ini', flush=True)
    print('CA publico:', ca, flush=True)
    env = os.environ.copy()
    env['NFS_PHP_DIR'] = str(php_dir)
    env['NFS_PHP_CA_FILE'] = str(ca)
    env['PHPRC'] = str(php_dir / 'php.ini')
    scan = ROOT / 'build/php_ini_scan_vazio'
    scan.mkdir(parents=True, exist_ok=True)
    env['PHP_INI_SCAN_DIR'] = str(scan)
    # Sem -d: este teste precisa comprovar que o php.ini empacotado funciona.
    subprocess.run([str(php_dir / 'php.exe'), '-c', str(php_dir / 'php.ini'),
                    str(ROOT / 'installer_support/check_php.php'), str(ROOT)],
                   env=env, check=True, timeout=90)
    # Nao apagar build completo; sobrepor apenas os recursos administrados aqui.
    ignore = shutil.ignore_patterns('.env', '.env.*', '*.pfx', '*.p12', '*.log', '*.bak')
    shutil.copytree(php_dir, DIST / 'runtime/php', dirs_exist_ok=True, ignore=ignore)
    shutil.copytree(ROOT / 'vendor', DIST / 'vendor', dirs_exist_ok=True, ignore=ignore)
    for name in ('baixar_emitida.php', 'baixar_por_chave_com_manifestacao.php', 'config.php'):
        shutil.copy2(ROOT / name, DIST / name)
    # Recursos adicionais do projeto continuam sob responsabilidade do build original.
    hashes = {}
    for name in ('VC_redist.x64.exe', 'tesseract-setup.exe'):
        path = ROOT / 'prereqs' / name
        if path.is_file():
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    hashes['cacert.pem'] = hashlib.sha256(ca.read_bytes()).hexdigest()
    (ROOT / 'installer_support/build_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf8')
    print('\nPacote preparado em:', DIST)
    print('Proximo: abrir installer_dependencias.iss no Inno Setup 6.2.2 e compilar.')
    print('O instalador Visual C++ em prereqs/VC_redist.x64.exe e obrigatorio para compilar.')
    print('Tesseract e opcional: prereqs/tesseract-setup.exe.')
    print('Nao houve teste de consulta fiscal ou OCR real.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr)
        sys.exit(1)
