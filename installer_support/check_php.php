<?php
// Exit 0 = verificacao local aprovada. Nao consulta SEFAZ nem usa credenciais.
$root = $argv[1] ?? dirname(__DIR__);
$missing = [];
foreach (['curl', 'openssl', 'soap', 'mbstring', 'zip', 'dom', 'SimpleXML', 'xml', 'json'] as $extension) {
    if (!extension_loaded($extension)) $missing[] = $extension;
}
if (version_compare(PHP_VERSION, '8.1.0', '<')) $missing[] = 'PHP >= 8.1';
if ($missing) { fwrite(STDERR, 'Requisitos ausentes: ' . implode(', ', $missing) . PHP_EOL); exit(11); }
$ca = ini_get('curl.cainfo');
$opensslCa = ini_get('openssl.cafile');
if (!$ca || !is_file($ca) || !is_readable($ca) ||
    !$opensslCa || !is_file($opensslCa) || !is_readable($opensslCa)) {
    fwrite(STDERR, "CA bundle nao encontrado ou ilegivel.\n");
    fwrite(STDERR, 'INI carregado: ' . (php_ini_loaded_file() ?: '(nenhum)') . PHP_EOL);
    fwrite(STDERR, 'curl.cainfo: ' . ($ca ?: '(vazio)') . PHP_EOL);
    fwrite(STDERR, 'openssl.cafile: ' . ($opensslCa ?: '(vazio)') . PHP_EOL);
    fwrite(STDERR, 'NFS_PHP_CA_FILE: ' . (getenv('NFS_PHP_CA_FILE') ?: '(vazio)') . PHP_EOL);
    exit(12);
}
try {
    $autoload = $root . '/vendor/autoload.php';
    if (!is_file($autoload)) throw new RuntimeException('vendor/autoload.php ausente');
    require $autoload;
    if (!class_exists('NFePHP\\NFe\\Tools')) throw new RuntimeException('Classe NFePHP\\NFe\\Tools ausente');
    foreach (['baixar_emitida.php', 'baixar_por_chave_com_manifestacao.php', 'config.php'] as $name) {
        if (!is_file($root . '/' . $name)) throw new RuntimeException('Script ausente: ' . $name);
    }
} catch (Throwable $e) { fwrite(STDERR, $e->getMessage() . PHP_EOL); exit(13); }
echo 'PHP ' . PHP_VERSION . ': extensoes, CA e autoload local OK.' . PHP_EOL;
exit(0);
