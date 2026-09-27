from __future__ import annotations

import asyncio
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app_config import (
    ADMIN_USER_IDS,
    ALLOWED_CHAT_IDS,
    BOT_TOKEN,
    DANFE_DIR,
    EXEMPLOS_DIR,
    LOG_DIR,
    NFSE_XML_DIR,
    PROCESSADOS_DIR,
)
from cadastros import (
    atualizar_perfil_telegram,
    cadastro_completo,
    inicializar_cadastros,
    interpretar_setor_nome,
    obter_cadastro,
    salvar_cadastro,
)
from extrator_chave import extrair_cnpj_destinatario_pdf, obter_chave
from fila_bot import (
    adicionar_na_fila,
    contar_aguardando,
    contar_pendentes_cadastro,
    inicializar_fila,
    liberar_pendentes_cadastro,
    listar_pendentes,
    marcar_aguardando,
    marcar_aguardando_cadastro,
    marcar_concluido,
    marcar_erro,
    marcar_processando,
    obter_item,
    registrar_intro,
    usuario_ja_viu_intro,
)
from historico import buscar_por_chave, inicializar, registrar, ultimo_sucesso
from nfe import consultar_nfe, extrair_cnpj_emitente_da_chave
from armazenamento import salvar_xml
from nfse import consultar_nfse
from roteamento import validar_destinatario
from xml_fiscal import extrair_dados_xml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "telegram_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("bot_fiscal_unificado")

EXEMPLO_PDF = EXEMPLOS_DIR / "DANFESe_v2_EXEMPLO.pdf"

FILA_PROCESSAMENTO: asyncio.Queue[int] = asyncio.Queue()
ITEM_PROCESSANDO_ATUAL: int | None = None

CONSULTA_FISCAL_LOCK = asyncio.Lock()


class ChatMessenger:
    def __init__(self, application: Application, chat_id: int):
        self.application = application
        self.chat_id = chat_id

    async def reply_text(self, texto: str):
        return await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=texto,
        )


def autorizado(update: Update) -> bool:
    return (
        not ALLOWED_CHAT_IDS
        or (
            update.effective_chat is not None
            and update.effective_chat.id in ALLOWED_CHAT_IDS
        )
    )


def administrador(update: Update) -> bool:
    user = update.effective_user
    return autorizado(update) and (
        not ADMIN_USER_IDS
        or (user is not None and user.id in ADMIN_USER_IDS)
    )


def limpar_nome(nome: str) -> str:
    nome = Path(nome).name
    return re.sub(r'[<>:"/\\|?*]', "_", nome)


def caminho_unico(pasta: Path, nome: str) -> Path:
    destino = pasta / limpar_nome(nome)
    if not destino.exists():
        return destino

    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return pasta / f"{destino.stem}_{marca}{destino.suffix}"


def mover_processado(pdf: Path) -> Path:
    destino = caminho_unico(PROCESSADOS_DIR, pdf.name)
    return Path(shutil.move(str(pdf), str(destino)))


def atualizar_perfil_do_update(update: Update) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    atualizar_perfil_telegram(
        telegram_user_id=user.id,
        chat_id=chat.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )


async def liberar_fila_apos_cadastro(user_id: int) -> int:
    ids = liberar_pendentes_cadastro(user_id)
    for item_id in ids:
        await FILA_PROCESSAMENTO.put(item_id)
    return len(ids)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorizado(update):
        await update.message.reply_text("Acesso não autorizado.")
        return

    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    atualizar_perfil_do_update(update)

    if not usuario_ja_viu_intro(user.id):
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "👋 Seja bem-vindo ao Bot Fiscal Unificado.\n\n"
                "Envie um PDF de NF-e ou NFS-e Nacional.\n\n"
                "O bot extrai a chave por texto/OCR, obtém o XML e salva na "
                "pasta configurada pelo CNPJ do destinatário.\n\n"
                "No primeiro envio de uma Nota de Serviço, será solicitado "
                "Setor + Nome completo. Esse cadastro fica vinculado ao seu "
                "perfil permanente do Telegram.\n\n"
                "Se houver outro processamento, seu documento entrará na fila."
            ),
        )

        if EXEMPLO_PDF.is_file():
            with EXEMPLO_PDF.open("rb") as arquivo:
                await context.bot.send_document(
                    chat_id=chat.id,
                    document=arquivo,
                    caption="📎 Exemplo de documento fiscal aceito.",
                )

        registrar_intro(user.id, chat.id)
        return

    await update.message.reply_text(
        "🤖 Envie um PDF de NF-e ou NFS-e Nacional para iniciar."
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    aguardando = contar_aguardando()
    ocupado = ITEM_PROCESSANDO_ATUAL is not None

    await update.message.reply_text(
        ("🟡 Sistema processando.\n" if ocupado else "🟢 Sistema disponível.\n")
        + f"📋 Aguardando: {aguardando}"
    )


async def cadastro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorizado(update):
        await update.message.reply_text("Acesso não autorizado.")
        return
    atualizar_perfil_do_update(update)
    user = update.effective_user
    if user is None:
        return

    cadastro = obter_cadastro(user.id)
    if not cadastro_completo(user.id):
        await update.message.reply_text(
            "🪪 Você ainda não possui cadastro completo.\n\n"
            "Envie no formato:\nSetor + Nome completo\n\n"
            "Exemplo:\nQualidade  + Maria da Silva"
        )
        return

    username = cadastro.get("username") or "sem username"
    await update.message.reply_text(
        "🪪 CADASTRO ENCONTRADO\n\n"
        f"Setor: {cadastro['setor']}\n"
        f"Nome: {cadastro['nome_completo']}\n"
        f"Telegram: @{username}\n"
        f"User ID: {user.id}\n\n"
        "Esse vínculo continua válido mesmo que a conversa seja apagada."
    )


async def alterar_cadastro_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not autorizado(update):
        await update.message.reply_text("Acesso não autorizado.")
        return
    atualizar_perfil_do_update(update)
    user = update.effective_user
    if user is None:
        return

    texto = " ".join(context.args).strip()
    if not texto:
        await update.message.reply_text(
            "Use:\n/alterarcadastro Setor + Nome completo"
        )
        return
    try:
        setor, nome = interpretar_setor_nome(texto)
        salvar_cadastro(user.id, setor, nome)
    except ValueError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    liberados = await liberar_fila_apos_cadastro(user.id)
    complemento = (
        f"\n\n📄 {liberados} documento(s) liberado(s) para processamento."
        if liberados else ""
    )
    await update.message.reply_text(
        "✅ Cadastro atualizado.\n\n"
        f"Setor: {setor}\nNome: {nome}{complemento}"
    )


async def receber_cadastro_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not autorizado(update):
        await update.message.reply_text("Acesso não autorizado.")
        return
    atualizar_perfil_do_update(update)
    user = update.effective_user
    msg = update.message
    if user is None or msg is None or not msg.text:
        return

    pendentes = contar_pendentes_cadastro(user.id)
    if cadastro_completo(user.id) and pendentes == 0:
        cadastro = obter_cadastro(user.id) or {}
        await msg.reply_text(
            "ℹ️ Você já está cadastrado.\n\n"
            f"Setor: {cadastro.get('setor', '')}\n"
            f"Nome: {cadastro.get('nome_completo', '')}\n\n"
            "Para mudar, use:\n/alterarcadastro Setor + Nome completo"
        )
        return

    try:
        setor, nome = interpretar_setor_nome(msg.text)
        salvar_cadastro(user.id, setor, nome)
    except ValueError as exc:
        await msg.reply_text(
            f"⚠️ {exc}\n\n"
            "Exemplo:\nQualidade + Maria Aparecida da Silva"
        )
        return

    liberados = await liberar_fila_apos_cadastro(user.id)
    await msg.reply_text(
        "✅ CADASTRO SALVO\n\n"
        f"Setor: {setor}\n"
        f"Nome: {nome}\n"
        f"User ID permanente: {user.id}\n\n"
        "Você não precisará informar novamente, mesmo que apague a conversa."
        + (
            f"\n\n📄 {liberados} documento(s) liberado(s) para processamento."
            if liberados else ""
        )
    )


async def consultar_envio_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not administrador(update):
        await update.message.reply_text("Acesso administrativo não autorizado.")
        return
    if not context.args:
        await update.message.reply_text("Use: /consultar CHAVE_FISCAL")
        return

    chave = re.sub(r"\D", "", "".join(context.args))
    if len(chave) not in (44, 50):
        await update.message.reply_text("⚠️ Informe uma chave de 44 ou 50 dígitos.")
        return

    registros = buscar_por_chave(chave, limite=5)
    if not registros:
        await update.message.reply_text(
            "🔎 Nenhum processamento concluído encontrado para essa chave."
        )
        return

    blocos = []
    for registro in registros:
        username = registro.get("telegram_username") or "sem username"
        blocos.append(
            "\n".join(
                (
                    f"Data: {registro.get('criado_em') or '-'}",
                    f"Tipo: {registro.get('tipo_documento') or '-'}",
                    f"Nome: {registro.get('solicitante_nome') or 'não informado'}",
                    f"Setor: {registro.get('solicitante_setor') or 'não informado'}",
                    f"Telegram: @{username}",
                    f"User ID: {registro.get('telegram_user_id') or '-'}",
                    f"Chat ID: {registro.get('telegram_chat_id') or '-'}",
                    f"Destino: {registro.get('xml_destino') or '-'}",
                )
            )
        )

    await update.message.reply_text(
        "🔎 HISTÓRICO DO ENVIO\n\n" + "\n\n---\n\n".join(blocos)
    )


async def processar_documento(
    msg: ChatMessenger,
    pdf: Path,
    chave: str,
    metodo: str,
    tipo: str,
    solicitante: dict | None,
) -> bool:
    # 1) DEDUPLICAÇÃO POR HISTÓRICO CONCLUÍDO
    anterior = ultimo_sucesso(chave)
    if anterior:
        await msg.reply_text(
            "⚠️ Este documento fiscal já foi processado anteriormente.\n\n"
            f"🔑 Chave:\n{chave}\n\n"
            "✅ Nenhuma nova importação será realizada."
        )
        return True

    await msg.reply_text(
        f"✅ Documento identificado como {tipo}.\n\n"
        f"🔑 Chave:\n{chave}\n"
        f"🔍 Método: {metodo}"
    )

    # 2) OBTENÇÃO DO XML PELO FLUXO CORRETO
    if tipo == "NFSE":
        xml_existente = NFSE_XML_DIR / f"{chave}.xml"
        if xml_existente.is_file():
            xml = xml_existente
            status = "XML_COMPLETO"
            detalhe = "XML NFS-e local reutilizado."
            await msg.reply_text(
                "📂 XML NFS-e já encontrado localmente. A consulta será ignorada."
            )
        else:
            await msg.reply_text("🌐 Consultando a Sefin Nacional...")
            async with CONSULTA_FISCAL_LOCK:
                status, detalhe, xml = await asyncio.to_thread(
                    consultar_nfse,
                    chave,
                )
    else:
        cnpj_emitente = extrair_cnpj_emitente_da_chave(chave)
        await msg.reply_text(
            "🌐 Consultando a Distribuição DF-e da SEFAZ...\n"
            f"🏢 CNPJ do emitente na chave: {cnpj_emitente or 'não identificado'}"
        )
        async with CONSULTA_FISCAL_LOCK:
            status, detalhe, xml = await asyncio.to_thread(
                consultar_nfe,
                chave,
            )

    if status != "XML_COMPLETO" or xml is None or not xml.is_file():
        await msg.reply_text(
            "❌ Não foi possível obter o XML.\n\n"
            f"Status: {status}\n"
            f"Detalhe: {detalhe}"
        )
        return False

    # 3) EXTRAI DESTINATÁRIO DO XML. O PDF só é fallback.
    dados = extrair_dados_xml(xml, tipo)
    tipo_real = dados["tipo"] if dados["tipo"] in {"NFE", "NFSE"} else tipo
    documento = dados["cnpj_destinatario"] or extrair_cnpj_destinatario_pdf(pdf)

    if not documento:
        await msg.reply_text(
            "❌ CNPJ/CPF do destinatário não encontrado no XML nem no PDF."
        )
        return False

    try:
        documento, empresa_destino = validar_destinatario(documento)
    except ValueError as exc:
        await msg.reply_text(f"❌ Envio bloqueado por segurança.\n\n{exc}")
        return False

    await msg.reply_text(
        "✅ XML obtido.\n\n"
        f"🧾 Tipo: {tipo_real}\n"
        f"🧾 Nota: {dados['numero'] or 'Não identificada'}\n"
        f"🏢 Emitente/Prestador: {dados['emitente'] or 'Não identificado'}\n"
        f"📥 Destinatário/Tomador: {dados['destinatario'] or empresa_destino}\n"
        f"🆔 CNPJ de destino: {documento}"
    )

    # 4) SALVA O XML NO DESTINO CONFIGURADO
    await msg.reply_text("📂 Salvando XML na pasta configurada...")

    resultado = await asyncio.to_thread(
        salvar_xml,
        xml,
        documento,
        tipo_real,
    )

    arquivo_destino = resultado.get("arquivo_destino", "")

    # 5) MARCA CONCLUÍDO SOMENTE APÓS A CÓPIA DO XML
    registrar(
        chave=chave,
        tipo_documento=tipo_real,
        nota=dados["numero"],
        fornecedor=dados["emitente"],
        destinatario=dados["destinatario"] or empresa_destino,
        cnpj_destinatario=documento,
        origem_chave=metodo,
        xml_origem=str(xml),
        xml_destino=arquivo_destino,
        status="CONCLUIDO",
        telegram_user_id=(
            int(solicitante["telegram_user_id"]) if solicitante else None
        ),
        telegram_chat_id=msg.chat_id,
        telegram_username=(solicitante or {}).get("username"),
        solicitante_nome=(solicitante or {}).get("nome_completo"),
        solicitante_setor=(solicitante or {}).get("setor"),
    )

    await msg.reply_text(
        "✅ PROCESSAMENTO CONCLUÍDO\n\n"
        f"📂 Destino:\n{arquivo_destino}"
    )

    return True


async def processar_item_fila(application: Application, item_id: int) -> bool:
    item = obter_item(item_id)
    if item is None:
        return True

    msg = ChatMessenger(application, int(item["chat_id"]))
    pdf = Path(item["local_pdf"])

    if not pdf.is_file():
        raise FileNotFoundError(f"PDF da fila não encontrado: {pdf}")

    await msg.reply_text(
        "🔔 Sua vez chegou!\n"
        "O documento será processado agora."
    )

    await msg.reply_text(
        "📄 Documento fiscal recebido.\n"
        "🔎 Analisando o PDF e procurando a chave de acesso..."
    )

    chave = item.get("chave")
    metodo = item.get("origem_chave")
    tipo = item.get("tipo_documento")
    if not chave or not metodo or tipo not in {"NFE", "NFSE"}:
        chave, metodo, tipo = await asyncio.to_thread(obter_chave, pdf)

    if not chave:
        await msg.reply_text("❌ Chave fiscal não encontrada.")
        return True

    if tipo not in {"NFE", "NFSE"}:
        await msg.reply_text(
            "❌ O documento não foi identificado como NF-e ou NFS-e Nacional."
        )
        return True

    solicitante = obter_cadastro(int(item["user_id"]))
    if tipo == "NFSE" and not cadastro_completo(int(item["user_id"])):
        marcar_aguardando_cadastro(item_id)
        await msg.reply_text(
            "🪪 Antes de processar esta Nota de Serviço, faça seu cadastro.\n\n"
            "Envie:\nSetor + Nome completo\n\n"
            "Exemplo:\nPacking House + João da Silva"
        )
        return False

    sucesso = await processar_documento(
        msg,
        pdf,
        chave,
        metodo,
        tipo,
        solicitante,
    )

    if sucesso and pdf.is_file():
        mover_processado(pdf)
    return True


async def worker_fila(application: Application) -> None:
    global ITEM_PROCESSANDO_ATUAL

    while True:
        item_id = await FILA_PROCESSAMENTO.get()
        ITEM_PROCESSANDO_ATUAL = item_id

        try:
            marcar_processando(item_id)
            finalizar_item = await processar_item_fila(application, item_id)
            if finalizar_item:
                marcar_concluido(item_id)

        except Exception as exc:
            logger.exception("Erro no item %s", item_id)
            marcar_erro(item_id, str(exc))

            item = obter_item(item_id)
            if item:
                await application.bot.send_message(
                    chat_id=int(item["chat_id"]),
                    text=(
                        "❌ Erro durante o processamento.\n\n"
                        f"{exc}"
                    ),
                )

        finally:
            ITEM_PROCESSANDO_ATUAL = None
            FILA_PROCESSAMENTO.task_done()


async def post_init(application: Application) -> None:
    inicializar_cadastros()
    inicializar_fila()

    # Recupera itens que ficaram pendentes após reinício.
    pendentes = listar_pendentes()

    for item in pendentes:
        item_id = int(item["id"])
        marcar_aguardando(item_id)
        await FILA_PROCESSAMENTO.put(item_id)

    # Compatível com versões em que ApplicationBuilder.post_start não existe.
    asyncio.create_task(
        worker_fila(application),
        name="worker-fila-importacao",
    )


async def receber_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorizado(update):
        await update.message.reply_text("Acesso não autorizado.")
        return

    msg = update.message
    user = update.effective_user

    if msg is None or msg.document is None or user is None:
        return

    atualizar_perfil_do_update(update)

    nome = msg.document.file_name or "danfese.pdf"

    if not nome.lower().endswith(".pdf"):
        await msg.reply_text("⚠️ Envie um arquivo PDF.")
        return

    destino = caminho_unico(DANFE_DIR, nome)

    await context.bot.send_chat_action(
        chat_id=msg.chat_id,
        action=ChatAction.TYPING,
    )

    arquivo = await msg.document.get_file()
    await arquivo.download_to_drive(custom_path=str(destino))

    await msg.reply_text(
        "📄 Documento recebido. Identificando o tipo e a chave fiscal..."
    )
    chave, metodo, tipo = await asyncio.to_thread(obter_chave, destino)
    if not chave or tipo not in {"NFE", "NFSE"}:
        await msg.reply_text(
            "❌ Não foi possível identificar uma NF-e ou NFS-e Nacional.\n\n"
            "O PDF ficou salvo para análise, mas não entrou na fila."
        )
        return

    esperando_antes = contar_aguardando()
    ocupado = ITEM_PROCESSANDO_ATUAL is not None
    precisa_cadastro = tipo == "NFSE" and not cadastro_completo(user.id)

    item_id = adicionar_na_fila(
        chat_id=msg.chat_id,
        user_id=user.id,
        file_id=msg.document.file_id,
        file_name=nome,
        local_pdf=str(destino),
        chave=chave,
        origem_chave=metodo,
        tipo_documento=tipo,
        status="AGUARDANDO_CADASTRO" if precisa_cadastro else "AGUARDANDO",
    )

    if precisa_cadastro:
        await msg.reply_text(
            "🧾 Nota de Serviço identificada.\n\n"
            "Como este é seu primeiro envio, informe:\n"
            "Setor + Nome completo\n\n"
            "Exemplo:\nQualidade + Maria Aparecida da Silva\n\n"
            "O documento ficou salvo e será liberado automaticamente depois "
            "do cadastro. O vínculo usa seu User ID do Telegram, então você "
            "não precisará cadastrar novamente se apagar a conversa."
        )
        return

    await FILA_PROCESSAMENTO.put(item_id)

    if ocupado:
        await msg.reply_text(
            "📥 Documento adicionado à fila.\n\n"
            "🟡 Existe uma importação em andamento.\n"
            f"📋 Sua posição: {esperando_antes + 1}\n\n"
            "Você será avisado quando chegar sua vez."
        )
    elif esperando_antes > 0:
        await msg.reply_text(
            "📥 Documento adicionado à fila.\n\n"
            f"📋 Sua posição: {esperando_antes + 1}"
        )
    else:
        await msg.reply_text(
            "📥 Documento recebido.\n"
            "🟢 O processamento começará em instantes."
        )


def main() -> None:
    inicializar()
    inicializar_cadastros()
    inicializar_fila()

    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado.")

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("cadastro", cadastro_cmd))
    app.add_handler(CommandHandler("alterarcadastro", alterar_cadastro_cmd))
    app.add_handler(CommandHandler("consultar", consultar_envio_cmd))
    app.add_handler(MessageHandler(filters.Document.PDF, receber_pdf))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receber_cadastro_texto)
    )

    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
