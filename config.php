<?php

declare(strict_types=1);

$senhaCertificado = trim((string)getenv('NFE_CERT_SENHA'));
$cnpj = preg_replace('/\D+/', '', (string)getenv('EMPRESA_CNPJ'));
$razaoSocial = trim((string)getenv('NFE_RAZAO_SOCIAL'));
$siglaUF = strtoupper(trim((string)getenv('NFE_UF')));
$caminhoCertificado = trim((string)getenv('NFE_CERT_PFX'));

if ($caminhoCertificado === '') {
    $caminhoCertificado = __DIR__
        . DIRECTORY_SEPARATOR
        . 'certificado'
        . DIRECTORY_SEPARATOR
        . 'empresa.pfx';
} elseif (
    !preg_match('/^[A-Za-z]:[\\\/]/', $caminhoCertificado)
    && !str_starts_with($caminhoCertificado, '\\')
    && !str_starts_with($caminhoCertificado, '/')
) {
    $caminhoCertificado = __DIR__ . DIRECTORY_SEPARATOR . $caminhoCertificado;
}

return [
    'tpAmb' => 1,
    'razaosocial' => $razaoSocial !== '' ? $razaoSocial : 'EMPRESA CONFIGURADA',
    'cnpj' => $cnpj,
    'siglaUF' => $siglaUF,
    'certificado' => $caminhoCertificado,
    'senhaCertificado' => $senhaCertificado,
    'proxyConf' => [
        'proxyIp' => '',
        'proxyPort' => '',
        'proxyUser' => '',
        'proxyPass' => '',
    ],
];
