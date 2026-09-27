# Bot Fiscal Unificado — NF-e e NFS-e

Bot em Python para receber documentos fiscais pelo Telegram, identificar NF-e/NFS-e, obter o XML oficial e salvá-lo em uma pasta configurável.

O projeto não depende de automação de tela ou navegador remoto. O destino pode ser uma pasta local, outra unidade ou um compartilhamento de rede acessível pela máquina que executa o bot.

## Fluxo

```text
PDF enviado no Telegram
        ↓
Extração da chave fiscal
        ↓
Consulta NF-e / NFS-e
        ↓
Leitura do destinatário/tomador no XML
        ↓
Validação opcional do CNPJ/CPF
        ↓
Cópia do XML para DESTINO_NFE ou DESTINO_NFSE
```

## Destino configurável

### Forma mais fácil

Depois de executar `configurar.bat`, dê dois cliques em:

```text
CONFIGURAR_DESTINOS.bat
```

O programa abre um seletor para a pasta de NF-e, outro para NFS-e e pergunta se deve criar uma subpasta por CNPJ/CPF. As escolhas são gravadas automaticamente no `.env`.

### Configuração manual

No `.env`:

```env
DESTINO_NFE=D:\Fiscal\NFE
DESTINO_NFSE=D:\Fiscal\NFSE
CRIAR_SUBPASTA_DOCUMENTO=1
```

Também é possível usar um compartilhamento UNC:

```env
DESTINO_NFE=\\SERVIDOR\Fiscal\NFE
DESTINO_NFSE=\\SERVIDOR\Fiscal\NFSE
```

Com `CRIAR_SUBPASTA_DOCUMENTO=1`, o formato será:

```text
<DESTINO>\<CNPJ-ou-CPF>\<arquivo.xml>
```

Com `CRIAR_SUBPASTA_DOCUMENTO=0`, o XML é salvo diretamente em `DESTINO_NFE` ou `DESTINO_NFSE`.

## Recursos principais

- extração por texto nativo do PDF e OCR/Tesseract;
- NF-e modelo 55 com chave de 44 dígitos e validação do DV;
- NFS-e Nacional com chave de 50 dígitos;
- consulta de NFS-e Nacional usando certificado A1/PFX;
- integração de NF-e via scripts PHP/NFePHP;
- fila persistente de processamento;
- bloqueio de duplicidade por chave fiscal;
- histórico SQLite;
- cadastro persistente do solicitante pelo Telegram User ID;
- whitelist opcional de CNPJ/CPF de destinatários.

## Instalação

No Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Depois edite `.env` e preencha apenas os dados da sua instalação.

Para o fluxo de NF-e, instale PHP e Composer e execute:

```powershell
composer install
```

O `composer.json` instala a biblioteca `nfephp-org/sped-nfe` usada pelos scripts PHP.

Também instale o Tesseract OCR se quiser fallback de OCR e ajuste `TESSERACT_EXE` no `.env`.

## Configuração

As principais opções estão em `.env.example`:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_ADMIN_USER_IDS=

EMPRESA_CNPJ=
NFE_CNPJS_EMITENTES_PROPRIOS=
NFE_RAZAO_SOCIAL=
NFE_UF=

NFSE_CERT_PFX=certificado/empresa.pfx
NFE_CERT_PFX=certificado/empresa.pfx
NFE_CERT_SENHA=

NFE_FILIAL_CNPJ=
NFE_FILIAL_CERT_PFX=certificado/filial.pfx
NFE_FILIAL_CERT_SENHA=

DESTINO_NFE=saida/NFE
DESTINO_NFSE=saida/NFSE
CRIAR_SUBPASTA_DOCUMENTO=1
```

Nunca coloque tokens, senhas ou certificados diretamente no código.

## Lista opcional de destinatários

`empresas_certificadas.example.json` contém somente dados fictícios.

Para usar a validação:

1. copie para `empresas_certificadas.json`;
2. coloque seus CNPJs reais apenas na cópia local;
3. defina `EXIGIR_CNPJ_CADASTRADO=1`.

O arquivo real `empresas_certificadas.json` está no `.gitignore`.

## Verificação antes de iniciar

Execute:

```powershell
.\.venv\Scripts\python.exe .\verificar_configuracao.py
```

O verificador testa também se `DESTINO_NFE` e `DESTINO_NFSE` têm permissão de escrita.

## Executar

```powershell
.\.venv\Scripts\python.exe .\bot_telegram.py
```

Ou use:

```text
INICIAR_BOT.bat
```

Como não existe mais automação de interface gráfica, o bot não precisa manter uma sessão de navegador/desktop aberta para copiar os XMLs.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para apenas analisar um PDF e visualizar o destino previsto:

```powershell
.\.venv\Scripts\python.exe .\testar_pdf.py "C:\caminho\nota.pdf"
```

## Arquivos principais

- `bot_telegram.py`: Telegram, fila e orquestração;
- `armazenamento.py`: cópia do XML para o destino escolhido;
- `app_config.py`: configuração central pelo `.env`;
- `cadastros.py`: perfis e cadastro de nome/setor;
- `extrator_chave.py`: texto, OCR e chave NF-e/NFS-e;
- `nfe.py`: integração com scripts PHP da NF-e;
- `nfse.py`: consulta à Sefin Nacional;
- `xml_fiscal.py`: leitura dos XMLs e identificação de destinatário;
- `roteamento.py`: validação opcional de CNPJ/CPF;
- `historico.py`: deduplicação e auditoria;
- `fila_bot.py`: fila persistente.


## Observação

Um PDF de NFS-e municipal sem chave Nacional de 50 dígitos não possui uma API única para baixar o XML. Nesses casos é necessário um conector específico para a prefeitura ou o XML já obtido por outro meio.

## License

Copyright © 2026 Paulo Ricardo Lopes Dionizio.

This project is publicly available for study and reference.

Use, modification, redistribution or commercial use requires
prior authorization from the author.

For permission, contact the repository owner.
