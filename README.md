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

A conta do Windows que executa o bot precisa ter permissão de acesso e escrita no destino.

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

### Pelo instalador Windows

Se você recebeu o instalador do aplicativo:

1. Execute o instalador.
2. Escolha a pasta de instalação.
3. Preencha as configurações solicitadas.
4. Caso utilize OCR, siga as instruções da seção **Tesseract OCR e idioma português**.
5. Conclua a instalação e execute o aplicativo pelo atalho criado.

Quando o pacote inclui PHP portátil e as dependências PHP, não é necessário instalar PHP e Composer separadamente.

O executável empacotado também dispensa a instalação do Python na máquina de destino.

### Pelo código-fonte

No PowerShell, dentro da pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Na primeira configuração, copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

> Se você já possui um `.env` configurado, preserve esse arquivo. Não o substitua pelo exemplo.

Depois edite `.env` e preencha os dados da sua instalação.

Para o fluxo de NF-e, instale PHP e Composer e execute na pasta que contém `composer.json`:

```powershell
composer install
```

O `composer.json` instala a biblioteca `nfephp-org/sped-nfe` usada pelos scripts PHP.

Se utilizar PHP portátil, configure o aplicativo para apontar para o executável correspondente.

## Tesseract OCR e idioma português

O Tesseract é utilizado para reconhecer texto em PDFs digitalizados ou imagens quando a extração de texto nativo não encontra a chave fiscal.

Para utilizar o OCR, disponibilize o Tesseract e os arquivos de idioma:

- `por.traineddata`: português;
- `eng.traineddata`: inglês, utilizado na tentativa alternativa de reconhecimento.

Instalar a biblioteca Python `pytesseract` não instala o executável do Tesseract nem os arquivos de idioma.

### Baixar o idioma português

Baixe o arquivo pelo link:

**[Baixar por.traineddata — português](https://github.com/tesseract-ocr/tessdata/raw/refs/heads/main/por.traineddata)**

Página oficial do arquivo:

https://github.com/tesseract-ocr/tessdata/blob/main/por.traineddata

Se acessar pela página do GitHub, use a opção **Download raw file**.

Não salve a página HTML: o arquivo precisa se chamar exatamente:

```text
por.traineddata
```

### Onde colocar o arquivo

Copie `por.traineddata` para a pasta **tessdata** da instalação do Tesseract que será utilizada pelo bot.

Por exemplo, se o executável estiver em:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

O arquivo de português deve ficar em:

```text
C:\Program Files\Tesseract-OCR\tessdata\por.traineddata
```

Mantenha também o arquivo:

```text
C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata
```

Caso o idioma inglês esteja ausente:

**[Baixar eng.traineddata — inglês](https://github.com/tesseract-ocr/tessdata/raw/refs/heads/main/eng.traineddata)**

> A pasta se chama `tessdata`, não `data`. Coloque os arquivos diretamente nela, sem criar outra pasta `tessdata` dentro da existente.

> Em `Program Files`, o Windows pode solicitar autorização de administrador para copiar os arquivos.

### Durante a instalação do Bot Fiscal

Se optar por utilizar OCR e o instalador solicitar o caminho do Tesseract:

1. Instale o Tesseract ou localize uma cópia completa dele.
2. Copie `por.traineddata` para a pasta `tessdata` correspondente.
3. Confira se `eng.traineddata` também está nessa pasta.
4. Volte ao instalador e selecione **tesseract.exe**.
5. Continue a instalação.

O campo do instalador deve apontar para o executável, por exemplo:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Não selecione o arquivo `por.traineddata` nesse campo.

Se os idiomas já estiverem incluídos no pacote do aplicativo, não será necessário baixá-los novamente.

### Tesseract portátil no projeto

Para preparar uma distribuição com OCR incluído, mantenha a cópia completa do Tesseract em:

```text
runtime\tesseract
```

Os caminhos dos arquivos principais serão:

```text
runtime\tesseract\tesseract.exe
runtime\tesseract\tessdata\por.traineddata
runtime\tesseract\tessdata\eng.traineddata
```

Preserve também as DLLs e os demais arquivos necessários ao funcionamento dessa distribuição do Tesseract. Copiar somente `tesseract.exe` e os idiomas pode não ser suficiente.

Inclua essa pasta na preparação do pacote e na distribuição do aplicativo.

### Configuração manual

Para configurar o executável no `.env`:

```env
TESSERACT_EXE=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Adapte o caminho caso o Tesseract esteja em outra pasta.

### Conferir os idiomas

No PowerShell, execute:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

Para verificar a cópia portátil a partir da pasta do projeto:

```powershell
& ".\runtime\tesseract\tesseract.exe" --list-langs --tessdata-dir ".\runtime\tesseract\tessdata"
```

A lista deve incluir:

```text
eng
por
```

Outros idiomas, como `osd`, também podem aparecer.

Se `por` não aparecer, confira se o arquivo foi colocado na pasta `tessdata` indicada pela saída do comando.

Após essa configuração, o reconhecimento OCR utiliza os arquivos locais e não precisa baixar o idioma a cada execução. As consultas fiscais e a comunicação com o Telegram continuam dependendo de internet.

## Configuração

Na instalação pelo aplicativo, o arquivo de configuração fica em:

```text
%LOCALAPPDATA%\NFS Extrator\.env
```

Você pode abrir essa pasta pelo Explorador de Arquivos, colando na barra de endereço:

```text
%LOCALAPPDATA%\NFS Extrator
```

Na execução pelo código-fonte, confira qual `.env` sua versão de `app_config.py` utiliza. A configuração do usuário pode ter prioridade sobre o `.env` da pasta do projeto.

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

Se utilizar um Tesseract externo, configure também:

```env
TESSERACT_EXE=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Nunca coloque tokens, senhas ou certificados diretamente no código.

Não publique o `.env` real, certificados `.pfx`/`.p12` ou arquivos que contenham credenciais.

## Lista opcional de destinatários

`empresas_certificadas.example.json` contém somente dados fictícios.

Para usar a validação:

1. copie para `empresas_certificadas.json`;
2. coloque seus CNPJs reais apenas na cópia local;
3. defina `EXIGIR_CNPJ_CADASTRADO=1`.

O arquivo real `empresas_certificadas.json` está no `.gitignore`.

## Verificação antes de iniciar

Para execução pelo código-fonte:

```powershell
.\.venv\Scripts\python.exe .\verificar_configuracao.py
```

O verificador testa também se `DESTINO_NFE` e `DESTINO_NFSE` têm permissão de escrita.

Se utilizar OCR, confira também os idiomas disponíveis no Tesseract conforme as instruções anteriores.

## Executar

### Aplicativo instalado

Execute pelo atalho criado durante a instalação.

### Código-fonte

Na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe .\bot_telegram.py
```

Ou use:

```text
INICIAR_BOT.bat
```

Como não existe mais automação de interface gráfica, o bot não precisa manter uma sessão de navegador/desktop aberta para copiar os XMLs.

A máquina precisa permanecer ligada, com o processo do bot em execução e acesso à internet.

## Testes

Para executar os testes pelo código-fonte:

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
