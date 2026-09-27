from __future__ import annotations

import json

from app_config import (
    BOT_TOKEN,
    DESTINO_NFE,
    DESTINO_NFSE,
    NFE_CNPJS_EMITENTES_PROPRIOS,
    NFE_SCRIPT_EMITIDA,
    NFE_SCRIPT_RECEBIDA,
    NFE_XML_DIR,
    NFSE_CERT_PFX,
    PHP_EXE,
)
from roteamento import carregar_empresas


def _ok(texto: str) -> None:
    print(f"[OK] {texto}")


def _aviso(texto: str) -> None:
    print(f"[AVISO] {texto}")


def _erro(texto: str) -> None:
    print(f"[ERRO] {texto}")


def main() -> int:
    erros = 0
    print("=" * 60)
    print("VERIFICACAO DO BOT FISCAL UNIFICADO")
    print("=" * 60)

    try:
        empresas = carregar_empresas()
        _ok(f"{len(empresas)} destinatário(s) cadastrado(s) na lista opcional.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _erro(f"empresas_certificadas.json inválido: {exc}")
        empresas = {}
        erros += 1

    if BOT_TOKEN:
        _ok("Token do Telegram preenchido.")
    else:
        _erro("TELEGRAM_BOT_TOKEN não foi preenchido no .env.")
        erros += 1

    print()
    print("CNPJs configurados como emitentes próprios:")
    if NFE_CNPJS_EMITENTES_PROPRIOS:
        for cnpj in sorted(NFE_CNPJS_EMITENTES_PROPRIOS):
            print(f"       {cnpj}")
    else:
        _aviso("Nenhum CNPJ próprio configurado para o fluxo de NF-e emitida.")

    verificacoes = (
        ("PHP", PHP_EXE, True),
        ("Script de NF-e recebida", NFE_SCRIPT_RECEBIDA, True),
        ("Script de NF-e emitida", NFE_SCRIPT_EMITIDA, False),
        ("Certificado da NFS-e Nacional", NFSE_CERT_PFX, False),
    )
    print()
    for descricao, caminho, obrigatorio in verificacoes:
        if caminho.is_file():
            _ok(f"{descricao}: {caminho}")
        elif obrigatorio:
            _erro(f"{descricao} não encontrado: {caminho}")
            erros += 1
        else:
            _aviso(f"{descricao} não encontrado: {caminho}")

    if NFE_XML_DIR.is_dir():
        _ok(f"Pasta temporária de XML NF-e: {NFE_XML_DIR}")
    else:
        _erro(f"Pasta temporária de XML NF-e não encontrada: {NFE_XML_DIR}")
        erros += 1

    for descricao, caminho in (
        ("Destino final de NF-e", DESTINO_NFE),
        ("Destino final de NFS-e", DESTINO_NFSE),
    ):
        try:
            caminho.mkdir(parents=True, exist_ok=True)
            teste = caminho / ".teste_escrita_bot_fiscal"
            teste.write_text("ok", encoding="utf-8")
            teste.unlink(missing_ok=True)
            _ok(f"{descricao} com permissão de escrita: {caminho}")
        except OSError as exc:
            _erro(f"Sem acesso de escrita em {caminho}: {exc}")
            erros += 1

    print()
    if erros:
        _erro(f"Foram encontrados {erros} erro(s). Corrija o .env/arquivos.")
        return 1

    _ok("Configuração principal válida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
