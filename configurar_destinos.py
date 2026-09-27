from __future__ import annotations

from pathlib import Path
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"
ENV_EXEMPLO = BASE / ".env.example"


def _escapar_env(valor: str) -> str:
    # Não adiciona aspas: python-dotenv aceita caminhos Windows/UNC diretamente.
    return valor.strip()


def _atualizar_env(chaves: dict[str, str]) -> None:
    if not ENV.exists():
        if not ENV_EXEMPLO.exists():
            raise FileNotFoundError(".env.example não encontrado.")
        shutil.copy2(ENV_EXEMPLO, ENV)

    linhas = ENV.read_text(encoding="utf-8").splitlines()
    encontradas: set[str] = set()
    novas: list[str] = []

    for linha in linhas:
        if "=" not in linha or linha.lstrip().startswith("#"):
            novas.append(linha)
            continue
        chave = linha.split("=", 1)[0].strip()
        if chave in chaves:
            novas.append(f"{chave}={_escapar_env(chaves[chave])}")
            encontradas.add(chave)
        else:
            novas.append(linha)

    faltantes = [chave for chave in chaves if chave not in encontradas]
    if faltantes:
        novas.append("")
        novas.append("# Destinos definidos pelo configurador")
        for chave in faltantes:
            novas.append(f"{chave}={_escapar_env(chaves[chave])}")

    ENV.write_text("\n".join(novas).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    messagebox.showinfo(
        "Bot Fiscal - Destinos",
        "Escolha primeiro a pasta onde os XMLs de NF-e serão salvos.",
        parent=root,
    )
    destino_nfe = filedialog.askdirectory(
        title="Escolha a pasta de destino das NF-e",
        mustexist=False,
        parent=root,
    )
    if not destino_nfe:
        return 1

    messagebox.showinfo(
        "Bot Fiscal - Destinos",
        "Agora escolha a pasta onde os XMLs de NFS-e serão salvos.",
        parent=root,
    )
    destino_nfse = filedialog.askdirectory(
        title="Escolha a pasta de destino das NFS-e",
        mustexist=False,
        parent=root,
    )
    if not destino_nfse:
        return 1

    subpasta = messagebox.askyesno(
        "Organização por CNPJ/CPF",
        "Deseja criar automaticamente uma subpasta para cada CNPJ/CPF de destino?",
        parent=root,
    )

    _atualizar_env(
        {
            "DESTINO_NFE": destino_nfe,
            "DESTINO_NFSE": destino_nfse,
            "CRIAR_SUBPASTA_DOCUMENTO": "1" if subpasta else "0",
        }
    )

    messagebox.showinfo(
        "Configuração salva",
        "Os destinos foram gravados no arquivo .env.\n\n"
        f"NF-e: {destino_nfe}\n"
        f"NFS-e: {destino_nfse}\n"
        f"Subpasta por CNPJ/CPF: {'Sim' if subpasta else 'Não'}",
        parent=root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
