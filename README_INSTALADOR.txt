PACOTE INICIAL DO INSTALADOR — NFS EXTRATOR

Arquivos:
- installer.iss      -> script do Inno Setup
- LICENSE.txt        -> modelo inicial de contrato/licença
- AVISO_USO.txt      -> aviso destacado sobre uso comercial
- assets/README.txt  -> instruções para sua logo

Como usar:
1. Coloque estes arquivos na raiz do projeto.
2. Gere primeiro o executável com PyInstaller, para existir:
   dist\NFS_Extrator\NFS_Extrator.exe
3. Adicione sua identidade visual na pasta assets.
4. Revise LICENSE.txt e preencha cidade/UF e e-mail.
5. Abra installer.iss no Inno Setup e compile.
6. O resultado será criado em:
   output\NFS_Extrator_Setup_v1.0.1.exe

IMPORTANTE:
O LICENSE.txt fornecido é um rascunho técnico e não substitui revisão jurídica.
