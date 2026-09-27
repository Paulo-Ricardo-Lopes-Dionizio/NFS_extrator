from __future__ import annotations

import sys
from pathlib import Path

from armazenamento import montar_destino_local
from extrator_chave import extrair_cnpj_destinatario_pdf, obter_chave


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python testar_pdf.py CAMINHO_DO_PDF")
        return 2

    pdf = Path(sys.argv[1])
    if not pdf.is_file():
        print(f"Arquivo não encontrado: {pdf}")
        return 2

    chave, metodo, tipo = obter_chave(pdf)
    documento = extrair_cnpj_destinatario_pdf(pdf)

    print(f"tipo={tipo}")
    print(f"chave={chave or ''}")
    print(f"metodo={metodo}")
    print(f"documento_destinatario_fallback={documento}")

    if chave and documento:
        arquivo = montar_destino_local(Path(f"{chave}.xml"), documento, tipo)
        print(f"destino_previsto={arquivo}")

    return 0 if chave else 1


if __name__ == "__main__":
    raise SystemExit(main())
