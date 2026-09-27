<?php

declare(strict_types=1);

require __DIR__ . '/vendor/autoload.php';

use NFePHP\NFe\Tools;
use NFePHP\Common\Certificate;

function sair(string $resultado, string $mensagem = ''): never
{
    if ($mensagem !== '') {
        echo $mensagem . PHP_EOL;
    }

    echo 'RESULTADO=' . $resultado . PHP_EOL;
    exit(0);
}

if ($argc < 2) {
    echo "Uso:\n";
    echo "php baixar_emitida_empresa.php CHAVE_NFE\n";
    exit(1);
}

$chave = preg_replace('/\D/', '', (string)$argv[1]);

if (!preg_match('/^\d{44}$/', $chave)) {
    echo "ERRO: chave precisa ter 44 dígitos.\n";
    exit(1);
}

$senhaCertificado = trim((string)getenv('NFE_FILIAL_CERT_SENHA'));
$cnpjFilial = preg_replace(
    '/\D/',
    '',
    (string)getenv('NFE_FILIAL_CNPJ')
);

if ($senhaCertificado === '') {
    echo "ERRO: NFE_FILIAL_CERT_SENHA não configurada.\n";
    exit(1);
}

if (!preg_match('/^\d{14}$/', $cnpjFilial)) {
    echo "ERRO: NFE_FILIAL_CNPJ não configurado ou inválido.\n";
    exit(1);
}

$caminhoCertificado = trim((string)getenv('NFE_FILIAL_CERT_PFX'));
if ($caminhoCertificado === '') {
    $caminhoCertificado = __DIR__
        . DIRECTORY_SEPARATOR
        . 'certificado'
        . DIRECTORY_SEPARATOR
        . 'filial.pfx';
}
elseif (
    !preg_match('/^[A-Za-z]:[\\\/]/', $caminhoCertificado)
    && !str_starts_with($caminhoCertificado, '\\')
    && !str_starts_with($caminhoCertificado, '/')
) {
    $caminhoCertificado = __DIR__ . DIRECTORY_SEPARATOR . $caminhoCertificado;
}

if (!is_file($caminhoCertificado)) {
    echo "ERRO: certificado alternativo não encontrado:\n";
    echo $caminhoCertificado . PHP_EOL;
    exit(1);
}

$pastaXml = __DIR__
    . DIRECTORY_SEPARATOR
    . 'xml';

$pastaCompletos = $pastaXml
    . DIRECTORY_SEPARATOR
    . 'completos';

$pastaResumos = $pastaXml
    . DIRECTORY_SEPARATOR
    . 'resumos';

foreach ([$pastaXml, $pastaCompletos, $pastaResumos] as $pasta) {
    if (!is_dir($pasta) && !mkdir($pasta, 0777, true) && !is_dir($pasta)) {
        throw new RuntimeException(
            'Não foi possível criar a pasta: ' . $pasta
        );
    }
}

$config = [
    'atualizacao' => date('Y-m-d H:i:s'),
    'tpAmb' => 1,
    'razaosocial' => 'CONSULTA NFE EMITIDA',
    'siglaUF' => 'SP',
    'cnpj' => $cnpjFilial,
    'schemes' => 'PL_009_V4',
    'versao' => '4.00',
    'tokenIBPT' => '',
    'CSC' => '',
    'CSCid' => '',
    'proxyConf' => [
        'proxyIp' => '',
        'proxyPort' => '',
        'proxyUser' => '',
        'proxyPass' => '',
    ],
];

try {
    echo str_repeat('=', 72) . PHP_EOL;
    echo "NF-e EMITIDA PELA EMPRESA - CONSULTA COM CERTIFICADO ALTERNATIVO\n";
    echo str_repeat('=', 72) . PHP_EOL;
    echo 'Chave: ' . $chave . PHP_EOL;
    echo 'CNPJ da configuração: ' . $cnpjFilial . PHP_EOL;
    echo PHP_EOL;

    $conteudoPfx = file_get_contents($caminhoCertificado);

    if ($conteudoPfx === false) {
        throw new RuntimeException(
            'Não foi possível ler o certificado.'
        );
    }

    $certificado = Certificate::readPfx(
        $conteudoPfx,
        $senhaCertificado
    );

    $tools = new Tools(
        json_encode($config, JSON_UNESCAPED_UNICODE),
        $certificado
    );

    $tools->model(55);

    echo "Consultando Distribuição DF-e...\n";

    $response = $tools->sefazDownload($chave);

    $dom = new DOMDocument();

    if (!@$dom->loadXML($response)) {
        throw new RuntimeException(
            'A resposta da SEFAZ não pôde ser interpretada como XML.'
        );
    }

    $xpath = new DOMXPath($dom);

    $cStatNode = $xpath->query(
        '//*[local-name()="retDistDFeInt"]/*[local-name()="cStat"]'
    )->item(0);

    $xMotivoNode = $xpath->query(
        '//*[local-name()="retDistDFeInt"]/*[local-name()="xMotivo"]'
    )->item(0);

    $cStat = $cStatNode ? trim($cStatNode->textContent) : '';
    $xMotivo = $xMotivoNode ? trim($xMotivoNode->textContent) : '';

    echo 'cStat=' . $cStat . PHP_EOL;
    echo 'xMotivo=' . $xMotivo . PHP_EOL;
    echo PHP_EOL;

    if ($cStat === '656') {
        sair(
            'CONSUMO_INDEVIDO',
            'A SEFAZ informou consumo indevido.'
        );
    }

    if ($cStat === '137') {
        sair(
            'NENHUM_XML_EXTRAIDO',
            'Nenhum documento foi localizado para esta chave.'
        );
    }

    if ($cStat !== '138') {
        sair(
            'NENHUM_XML_EXTRAIDO',
            'A SEFAZ não retornou documento localizado.'
        );
    }

    $docZipNodes = $xpath->query(
        '//*[local-name()="loteDistDFeInt"]/*[local-name()="docZip"]'
    );

    if ($docZipNodes === false || $docZipNodes->length === 0) {
        sair(
            'NENHUM_XML_EXTRAIDO',
            'A resposta veio sem docZip.'
        );
    }

    $encontrouCompleto = false;
    $encontrouResumo = false;

    foreach ($docZipNodes as $docZipNode) {
        if (!$docZipNode instanceof DOMElement) {
            continue;
        }

        $schema = $docZipNode->getAttribute('schema');
        $nsu = $docZipNode->getAttribute('NSU');

        echo 'Schema: ' . $schema . PHP_EOL;

        if ($nsu !== '') {
            echo 'NSU: ' . $nsu . PHP_EOL;
        }

        $compactado = base64_decode(
            trim($docZipNode->textContent),
            true
        );

        if ($compactado === false) {
            echo "Aviso: falha ao decodificar docZip em Base64.\n";
            continue;
        }

        $xml = @gzdecode($compactado);

        if ($xml === false) {
            echo "Aviso: falha ao descompactar docZip.\n";
            continue;
        }

        $ehCompleto = (
            str_contains($xml, '<nfeProc')
            || str_contains($xml, '<NFe')
        );

        $ehResumo = str_contains($xml, '<resNFe');

        if ($ehCompleto) {
            $destino = $pastaCompletos
                . DIRECTORY_SEPARATOR
                . $chave
                . '.xml';

            if (file_put_contents($destino, $xml) === false) {
                throw new RuntimeException(
                    'Não foi possível salvar o XML completo.'
                );
            }

            echo 'Documento salvo: ' . $destino . PHP_EOL;
            $encontrouCompleto = true;
            continue;
        }

        if ($ehResumo) {
            $destino = $pastaResumos
                . DIRECTORY_SEPARATOR
                . $chave
                . '.xml';

            if (file_put_contents($destino, $xml) === false) {
                throw new RuntimeException(
                    'Não foi possível salvar o resumo.'
                );
            }

            echo 'Resumo salvo: ' . $destino . PHP_EOL;
            $encontrouResumo = true;
            continue;
        }

        echo "Documento recebido, mas o tipo não foi reconhecido.\n";
    }

    if ($encontrouCompleto) {
        sair('XML_COMPLETO');
    }

    if ($encontrouResumo) {
        sair('RESUMO_ENCONTRADO');
    }

    sair('NENHUM_XML_EXTRAIDO');

} catch (Throwable $e) {
    echo str_repeat('=', 72) . PHP_EOL;
    echo "ERRO\n";
    echo str_repeat('=', 72) . PHP_EOL;
    echo get_class($e) . PHP_EOL;
    echo $e->getMessage() . PHP_EOL;
    echo 'RESULTADO=ERRO' . PHP_EOL;
    exit(1);
}
