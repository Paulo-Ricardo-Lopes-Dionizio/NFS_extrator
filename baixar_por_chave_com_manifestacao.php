<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use NFePHP\Common\Certificate;
use NFePHP\NFe\Tools;

/*
|--------------------------------------------------------------------------
| baixar_por_chave_com_manifestacao.php
|--------------------------------------------------------------------------
|
| Versão unificada para NF-e normal e NFF (tpEmis = 3)
|
| Fluxo:
| 1. Valida a chave.
| 2. Consulta via sefazDownload().
| 3. Se vier XML completo (procNFe/nfeProc), salva e encerra.
| 4. Se vier apenas resNFe, realiza Ciência da Operação (210210).
| 5. Aceita:
|      135 = Evento registrado e vinculado à NF-e
|      573 = Duplicidade de evento
| 6. Aguarda 10 segundos e consulta novamente.
| 7. Se for NFF e a primeira distribuição retornar 217,
|    faz apenas UMA nova tentativa curta antes de desistir.
|
| IMPORTANTE:
| - Não usa sefazConsultaChave() como critério de existência da NF-e,
|   pois em NFF ela pode retornar 217 mesmo quando a Distribuição DF-e
|   encontra o documento.
| - Não executa loops repetitivos para evitar consumo indevido.
|
*/

function encerrarComErro(string $mensagem, int $codigo = 1): never
{
    fwrite(STDERR, 'ERRO: ' . $mensagem . PHP_EOL);
    exit($codigo);
}

function garantirPasta(string $pasta): void
{
    if (
        !is_dir($pasta)
        && !mkdir($pasta, 0775, true)
        && !is_dir($pasta)
    ) {
        throw new RuntimeException(
            'Não foi possível criar a pasta: ' . $pasta
        );
    }
}

function somenteDigitos(string $valor): string
{
    return preg_replace('/\D/', '', $valor) ?? '';
}

function calcularDV(string $base): int
{
    if (!preg_match('/^\d{43}$/', $base)) {
        throw new RuntimeException(
            'A base da chave deve possuir 43 dígitos.'
        );
    }

    $peso = 2;
    $soma = 0;

    for ($i = 42; $i >= 0; $i--) {
        $soma += ((int) $base[$i]) * $peso;
        $peso++;

        if ($peso > 9) {
            $peso = 2;
        }
    }

    $digito = 11 - ($soma % 11);

    return in_array($digito, [10, 11], true)
        ? 0
        : $digito;
}

function chaveValida(string $chave): bool
{
    return (
        preg_match('/^\d{44}$/', $chave) === 1
        && calcularDV(substr($chave, 0, 43))
            === (int) $chave[43]
    );
}

function obterTpEmis(string $chave): int
{
    if (!preg_match('/^\d{44}$/', $chave)) {
        return -1;
    }

    // Índice zero-based 34 dentro da chave de 44 dígitos.
    return (int) $chave[34];
}

function valorTag(DOMDocument $dom, string $tag): string
{
    $lista = $dom->getElementsByTagName($tag);

    return $lista->length > 0
        ? trim((string) $lista->item(0)?->nodeValue)
        : '';
}

function nomeSeguro(string $valor): string
{
    return preg_replace(
        '/[^a-zA-Z0-9_.-]/',
        '_',
        $valor
    ) ?: 'documento';
}

/**
 * Lê especificamente o retorno interno do evento.
 *
 * O XML pode trazer:
 *  cStat 128 = lote processado
 * e dentro de retEvento:
 *  cStat 135 = evento registrado
 *  cStat 573 = duplicidade
 *
 * @return array{cStat:string,xMotivo:string}
 */
function lerRetEvento(DOMDocument $dom): array
{
    $retEventos = $dom->getElementsByTagName('retEvento');

    if ($retEventos->length === 0) {
        return [
            'cStat' => '',
            'xMotivo' => '',
        ];
    }

    $retEvento = $retEventos->item(0);

    if (!$retEvento instanceof DOMElement) {
        return [
            'cStat' => '',
            'xMotivo' => '',
        ];
    }

    $cStats = $retEvento->getElementsByTagName('cStat');
    $motivos = $retEvento->getElementsByTagName('xMotivo');

    return [
        'cStat' => $cStats->length > 0
            ? trim((string) $cStats->item(0)?->nodeValue)
            : '',
        'xMotivo' => $motivos->length > 0
            ? trim((string) $motivos->item(0)?->nodeValue)
            : '',
    ];
}

/**
 * @return array{
 *   cStat:string,
 *   xMotivo:string,
 *   completo:bool,
 *   resumo:bool,
 *   caminhoCompleto:?string
 * }
 */
function processarDistribuicao(
    string $resposta,
    string $chave,
    string $etapa,
    string $pastaRetornos,
    string $pastaCompletos,
    string $pastaResumos,
    string $pastaEventos,
    string $pastaOutros
): array {
    $timestamp = date('Y-m-d_H-i-s');

    $arquivoRetorno = $pastaRetornos
        . DIRECTORY_SEPARATOR
        . $chave
        . '_'
        . nomeSeguro($etapa)
        . '_'
        . $timestamp
        . '.xml';

    if (file_put_contents($arquivoRetorno, $resposta) === false) {
        throw new RuntimeException(
            'Falha ao salvar retorno da SEFAZ.'
        );
    }

    $dom = new DOMDocument();

    if (!$dom->loadXML($resposta)) {
        throw new RuntimeException(
            'Resposta da SEFAZ não é XML válido.'
        );
    }

    $cStat = valorTag($dom, 'cStat');
    $xMotivo = valorTag($dom, 'xMotivo');

    echo 'cStat: '
        . ($cStat ?: 'não informado')
        . PHP_EOL;

    echo 'Motivo: '
        . ($xMotivo ?: 'não informado')
        . PHP_EOL;

    echo 'Retorno bruto salvo em: '
        . $arquivoRetorno
        . PHP_EOL;

    $completo = false;
    $resumo = false;
    $caminhoCompleto = null;

    foreach ($dom->getElementsByTagName('docZip') as $doc) {
        if (!$doc instanceof DOMElement) {
            continue;
        }

        $schema = $doc->getAttribute('schema');
        $nsu = $doc->getAttribute('NSU');

        $binario = base64_decode(
            trim($doc->nodeValue),
            true
        );

        if ($binario === false) {
            echo 'AVISO: docZip inválido em base64.'
                . PHP_EOL;
            continue;
        }

        $xml = gzdecode($binario);

        if ($xml === false) {
            echo 'AVISO: não foi possível descompactar docZip.'
                . PHP_EOL;
            continue;
        }

        $schemaMin = strtolower($schema);

        if (
            str_contains($schemaMin, 'procnfe')
            || str_contains($schemaMin, 'nfeproc')
        ) {
            $pastaDestino = $pastaCompletos;
            $tipo = 'XML_COMPLETO';
            $completo = true;
        } elseif (str_contains($schemaMin, 'resnfe')) {
            $pastaDestino = $pastaResumos;
            $tipo = 'RESUMO';
            $resumo = true;
        } elseif (
            str_contains($schemaMin, 'procevento')
            || str_contains($schemaMin, 'retevento')
        ) {
            $pastaDestino = $pastaEventos;
            $tipo = 'EVENTO';
        } else {
            $pastaDestino = $pastaOutros;
            $tipo = 'OUTRO';
        }

        $nome = $chave
            . '_'
            . ($nsu !== '' ? $nsu : 'sem_nsu')
            . '_'
            . nomeSeguro(
                $schema !== '' ? $schema : 'sem_schema'
            )
            . '.xml';

        $destino = $pastaDestino
            . DIRECTORY_SEPARATOR
            . $nome;

        if (file_put_contents($destino, $xml) === false) {
            throw new RuntimeException(
                'Falha ao salvar documento extraído.'
            );
        }

        echo 'Documento salvo: '
            . $destino
            . PHP_EOL;

        echo 'Tipo: '
            . $tipo
            . PHP_EOL;

        if ($tipo === 'XML_COMPLETO') {
            $caminhoCompleto = $destino;
        }
    }

    return [
        'cStat' => $cStat,
        'xMotivo' => $xMotivo,
        'completo' => $completo,
        'resumo' => $resumo,
        'caminhoCompleto' => $caminhoCompleto,
    ];
}

$chave = somenteDigitos($argv[1] ?? '');

if ($chave === '') {
    encerrarComErro(
        'Informe a chave de acesso. Exemplo: '
        . 'php baixar_por_chave_com_manifestacao.php CHAVE'
    );
}

if (!chaveValida($chave)) {
    encerrarComErro(
        'Chave inválida ou dígito verificador incorreto.'
    );
}

$config = require __DIR__ . '/config.php';

$cnpj = somenteDigitos((string) ($config['cnpj'] ?? ''));
$senha = (string) ($config['senhaCertificado'] ?? '');
$pfx = (string) ($config['certificado'] ?? '');
$tpAmb = (int) ($config['tpAmb'] ?? 1);
$razaoSocial = (string) ($config['razaosocial'] ?? '');
$siglaUF = strtoupper(
    (string) ($config['siglaUF'] ?? '')
);
$proxyConf = $config['proxyConf'] ?? [
    'proxyIp' => '',
    'proxyPort' => '',
    'proxyUser' => '',
    'proxyPass' => '',
];

if ($cnpj === '') {
    encerrarComErro(
        'CNPJ não configurado em config.php.'
    );
}

if ($pfx === '' || !is_file($pfx)) {
    encerrarComErro(
        'Certificado não encontrado: ' . $pfx
    );
}

if ($senha === '') {
    encerrarComErro(
        'Senha do certificado não configurada.'
    );
}

if ($siglaUF === '') {
    encerrarComErro(
        'UF não configurada em config.php.'
    );
}

$base = __DIR__;

$pastaRetornos = $base
    . DIRECTORY_SEPARATOR
    . 'retornos';

$pastaManifestacoes = $base
    . DIRECTORY_SEPARATOR
    . 'manifestacoes';

$pastaCompletos = $base
    . DIRECTORY_SEPARATOR
    . 'xml'
    . DIRECTORY_SEPARATOR
    . 'completos';

$pastaResumos = $base
    . DIRECTORY_SEPARATOR
    . 'xml'
    . DIRECTORY_SEPARATOR
    . 'resumos';

$pastaEventos = $base
    . DIRECTORY_SEPARATOR
    . 'xml'
    . DIRECTORY_SEPARATOR
    . 'eventos';

$pastaOutros = $base
    . DIRECTORY_SEPARATOR
    . 'xml'
    . DIRECTORY_SEPARATOR
    . 'outros';

foreach (
    [
        $pastaRetornos,
        $pastaManifestacoes,
        $pastaCompletos,
        $pastaResumos,
        $pastaEventos,
        $pastaOutros,
    ] as $pasta
) {
    garantirPasta($pasta);
}

try {
    $conteudoPfx = file_get_contents($pfx);

    if ($conteudoPfx === false) {
        throw new RuntimeException(
            'Falha ao ler o certificado PFX.'
        );
    }

    $certificado = Certificate::readPfx(
        $conteudoPfx,
        $senha
    );

    $configNFe = [
        'atualizacao' => date('Y-m-d H:i:s'),
        'tpAmb' => $tpAmb,
        'razaosocial' => $razaoSocial,
        'cnpj' => $cnpj,
        'siglaUF' => $siglaUF,
        'schemes' => 'PL_010_V1.30',
        'versao' => '4.00',
        'tokenIBPT' => '',
        'CSC' => '',
        'CSCid' => '',
        'proxyConf' => $proxyConf,
    ];

    $tools = new Tools(
        json_encode(
            $configNFe,
            JSON_UNESCAPED_UNICODE
            | JSON_UNESCAPED_SLASHES
            | JSON_THROW_ON_ERROR
        ),
        $certificado
    );

    $tools->model(55);
    $tools->setEnvironment($tpAmb);

    $tpEmis = obterTpEmis($chave);

    echo 'Consultando a chave: '
        . $chave
        . PHP_EOL;

    echo 'tpEmis: '
        . $tpEmis
        . ($tpEmis === 3 ? ' (NFF)' : '')
        . PHP_EOL;

    /*
    |--------------------------------------------------------------------------
    | 1ª CONSULTA - DISTRIBUIÇÃO DF-e
    |--------------------------------------------------------------------------
    */

    $resposta = $tools->sefazDownload($chave);

    $primeiro = processarDistribuicao(
        $resposta,
        $chave,
        'antes_manifestacao',
        $pastaRetornos,
        $pastaCompletos,
        $pastaResumos,
        $pastaEventos,
        $pastaOutros
    );

    /*
    |--------------------------------------------------------------------------
    | XML completo já disponível
    |--------------------------------------------------------------------------
    */

    if ($primeiro['completo']) {
        echo 'RESULTADO=XML_COMPLETO' . PHP_EOL;

        if ($primeiro['caminhoCompleto'] !== null) {
            echo 'XML='
                . $primeiro['caminhoCompleto']
                . PHP_EOL;
        }

        exit(0);
    }

    /*
    |--------------------------------------------------------------------------
    | NFF com 217 na primeira tentativa
    |--------------------------------------------------------------------------
    |
    | Em testes reais, uma NFF tpEmis=3 pode retornar 217 em uma tentativa
    | e posteriormente ser localizada pela Distribuição DF-e.
    |
    | Fazemos somente UMA nova tentativa curta, sem loop.
    |
    */

    if (
        $tpEmis === 3
        && $primeiro['cStat'] === '217'
    ) {
        echo PHP_EOL;
        echo 'NFF detectada com cStat 217.'
            . PHP_EOL;

        echo 'Aguardando 3 segundos para uma única nova tentativa...'
            . PHP_EOL;

        sleep(3);

        $respostaRetry = $tools->sefazDownload($chave);

        $primeiro = processarDistribuicao(
            $respostaRetry,
            $chave,
            'retry_nff',
            $pastaRetornos,
            $pastaCompletos,
            $pastaResumos,
            $pastaEventos,
            $pastaOutros
        );

        if ($primeiro['completo']) {
            echo 'RESULTADO=XML_COMPLETO' . PHP_EOL;

            if ($primeiro['caminhoCompleto'] !== null) {
                echo 'XML='
                    . $primeiro['caminhoCompleto']
                    . PHP_EOL;
            }

            exit(0);
        }
    }

    /*
    |--------------------------------------------------------------------------
    | Consumo indevido
    |--------------------------------------------------------------------------
    */

    if ($primeiro['cStat'] === '656') {
        echo 'RESULTADO=CONSUMO_INDEVIDO' . PHP_EOL;
        exit(7);
    }

    /*
    |--------------------------------------------------------------------------
    | Se não veio resumo, não há motivo para manifestar
    |--------------------------------------------------------------------------
    */

    if (!$primeiro['resumo']) {
        echo 'RESULTADO=NENHUM_XML_EXTRAIDO' . PHP_EOL;
        exit(2);
    }

    /*
    |--------------------------------------------------------------------------
    | RESUMO ENCONTRADO -> CIÊNCIA DA OPERAÇÃO
    |--------------------------------------------------------------------------
    */

    echo PHP_EOL;
    echo 'Resumo encontrado.'
        . PHP_EOL;

    echo 'Realizando Ciência da Operação...'
        . PHP_EOL;

    $respostaManifestacao = $tools->sefazManifesta(
        $chave,
        210210,
        '',
        1
    );

    $arquivoManifestacao = $pastaManifestacoes
        . DIRECTORY_SEPARATOR
        . $chave
        . '_ciencia_'
        . date('Y-m-d_H-i-s')
        . '.xml';

    if (
        file_put_contents(
            $arquivoManifestacao,
            $respostaManifestacao
        ) === false
    ) {
        throw new RuntimeException(
            'Falha ao salvar retorno da manifestação.'
        );
    }

    echo 'Manifestação salva em: '
        . $arquivoManifestacao
        . PHP_EOL;

    $domManifestacao = new DOMDocument();

    if (
        !$domManifestacao->loadXML(
            $respostaManifestacao
        )
    ) {
        throw new RuntimeException(
            'Resposta da manifestação não é XML válido.'
        );
    }

    /*
     * Lote normalmente retorna 128.
     * O resultado real fica dentro de retEvento.
     */
    $cStatLote = valorTag(
        $domManifestacao,
        'cStat'
    );

    $xMotivoLote = valorTag(
        $domManifestacao,
        'xMotivo'
    );

    $evento = lerRetEvento(
        $domManifestacao
    );

    echo 'cStat lote: '
        . ($cStatLote ?: 'não informado')
        . PHP_EOL;

    echo 'Motivo lote: '
        . ($xMotivoLote ?: 'não informado')
        . PHP_EOL;

    echo 'cStat evento: '
        . ($evento['cStat'] ?: 'não informado')
        . PHP_EOL;

    echo 'Motivo evento: '
        . ($evento['xMotivo'] ?: 'não informado')
        . PHP_EOL;

    /*
     * 135 = Ciência registrada com sucesso.
     * 573 = evento já havia sido registrado.
     */
    if (
        !in_array(
            $evento['cStat'],
            ['135', '573'],
            true
        )
    ) {
        echo 'RESULTADO=MANIFESTACAO_REJEITADA'
            . PHP_EOL;

        exit(4);
    }

    /*
    |--------------------------------------------------------------------------
    | NOVA CONSULTA APÓS MANIFESTAÇÃO
    |--------------------------------------------------------------------------
    */

    echo PHP_EOL;
    echo 'Aguardando 10 segundos...'
        . PHP_EOL;

    sleep(10);

    echo 'Consultando novamente após manifestação...'
        . PHP_EOL;

    $segundaResposta = $tools->sefazDownload(
        $chave
    );

    $segundo = processarDistribuicao(
        $segundaResposta,
        $chave,
        'apos_manifestacao',
        $pastaRetornos,
        $pastaCompletos,
        $pastaResumos,
        $pastaEventos,
        $pastaOutros
    );

    if ($segundo['completo']) {
        echo 'RESULTADO=XML_COMPLETO' . PHP_EOL;

        if ($segundo['caminhoCompleto'] !== null) {
            echo 'XML='
                . $segundo['caminhoCompleto']
                . PHP_EOL;
        }

        exit(0);
    }

    if ($segundo['cStat'] === '656') {
        echo 'RESULTADO=CONSUMO_INDEVIDO' . PHP_EOL;
        exit(7);
    }

    if ($segundo['resumo']) {
        echo 'RESULTADO=RESUMO_ENCONTRADO'
            . PHP_EOL;

        exit(3);
    }

    echo 'RESULTADO=NENHUM_XML_EXTRAIDO'
        . PHP_EOL;

    exit(2);

} catch (Throwable $erro) {
    encerrarComErro(
        $erro::class
        . ': '
        . $erro->getMessage()
    );
}
