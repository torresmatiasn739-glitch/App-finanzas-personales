"""
bot.py — Bot de Telegram para cargar transacciones.
Vinculación con usuario y contraseña de la app.
Soporta: texto libre y mensajes de voz.

Ejecutar:
    python bot.py

Requiere en .env:
    TELEGRAM_BOT_TOKEN=tu_token_aqui
"""

import os
import logging
import tempfile
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
)

from database import login_user, get_categories, add_transaction
from groq_utils import transcribe_audio, extract_transaction

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Estados del ConversationHandler
# ──────────────────────────────────────────────
ASK_USERNAME, ASK_PASSWORD, MAIN_MENU, CONFIRM_TX = range(4)

# ──────────────────────────────────────────────
# Teclados
# ──────────────────────────────────────────────
MENU_KB = ReplyKeyboardMarkup(
    [["💬 Cargar por texto", "🎙️ Cargar por voz"],
     ["❌ Cerrar sesión"]],
    resize_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    [["✅ Confirmar", "✏️ Cancelar"]],
    resize_keyboard=True,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _uid(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    return context.user_data.get("user_id")

def _fmt_tx(tx: dict, cats: list) -> str:
    cat_name = next((c[1] for c in cats if c[0] == tx.get("category_id")), "Sin categoría")
    tipo = "📥 Ingreso" if tx.get("type") == "income" else "📤 Gasto"
    return (
        f"{tipo}\n"
        f"💵 Monto: ${float(tx.get('amount', 0)):,.2f}\n"
        f"🏷️ Categoría: {cat_name}\n"
        f"📝 Descripción: {tx.get('description', '—')}\n"
        f"📅 Fecha: {tx.get('date', '—')}"
    )


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Si ya está logueado
    if _uid(context):
        await update.message.reply_text(
            "Ya tenés sesión activa. ¿Qué querés hacer?", reply_markup=MENU_KB)
        return MAIN_MENU

    await update.message.reply_text(
        "👋 Bienvenido al bot de *Finanzas Personales*.\n\n"
        "Para continuar ingresá tu usuario de la app:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_USERNAME


# ──────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────

async def ask_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["username"] = update.message.text.strip()
    await update.message.reply_text("🔑 Ahora ingresá tu contraseña:")
    return ASK_PASSWORD


async def ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text.strip()
    username = context.user_data.get("username", "")

    # Borrar el mensaje de contraseña por seguridad (no siempre posible)
    try:
        await update.message.delete()
    except Exception:
        pass

    user_id, err = login_user(username, password)
    if err:
        await update.message.reply_text(
            f"❌ {err}\n\nUsá /start para intentar de nuevo.")
        return ConversationHandler.END

    context.user_data["user_id"]  = user_id
    context.user_data["username"] = username
    await update.message.reply_text(
        f"✅ ¡Bienvenido, *{username}*!\n\n"
        "Podés cargar transacciones por texto o voz.",
        parse_mode="Markdown",
        reply_markup=MENU_KB,
    )
    return MAIN_MENU


# ──────────────────────────────────────────────
# Menú principal
# ──────────────────────────────────────────────

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if text == "❌ Cerrar sesión":
        context.user_data.clear()
        await update.message.reply_text(
            "👋 Sesión cerrada. Usá /start para volver a ingresar.",
            reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if text == "💬 Cargar por texto":
        await update.message.reply_text(
            "✍️ Escribí la transacción en lenguaje natural.\n\n"
            "Ejemplos:\n"
            "• _Gasté 1500 en el supermercado hoy_\n"
            "• _Cobré 80000 de sueldo_\n"
            "• _Pagué 15000 de alquiler ayer_",
            parse_mode="Markdown",
        )
        context.user_data["mode"] = "text"
        return MAIN_MENU

    if text == "🎙️ Cargar por voz":
        await update.message.reply_text(
            "🎙️ Enviá un mensaje de voz describiendo la transacción.")
        context.user_data["mode"] = "voice"
        return MAIN_MENU

    # Texto libre — procesar transacción
    if context.user_data.get("mode") == "text":
        return await _process_text(update, context, update.message.text)

    await update.message.reply_text("Usá los botones del menú.", reply_markup=MENU_KB)
    return MAIN_MENU


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    uid  = _uid(context)
    cats = get_categories(uid)
    try:
        tx = extract_transaction(text, cats)
        context.user_data["pending_tx"] = tx
        await update.message.reply_text(
            f"Detecté esta transacción:\n\n{_fmt_tx(tx, cats)}\n\n¿Confirmás?",
            reply_markup=CONFIRM_KB,
        )
        return CONFIRM_TX
    except Exception as e:
        await update.message.reply_text(
            f"❌ No pude interpretar la transacción: {e}\n\nIntentá de nuevo.",
            reply_markup=MENU_KB)
        return MAIN_MENU


# ──────────────────────────────────────────────
# Voz
# ──────────────────────────────────────────────

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = _uid(context)
    if not uid:
        await update.message.reply_text("Usá /start para iniciar sesión.")
        return ConversationHandler.END

    await update.message.reply_text("⏳ Procesando tu audio...")

    voice     = update.message.voice
    tg_file   = await voice.get_file()
    audio_bytes = await tg_file.download_as_bytearray()

    try:
        transcription = transcribe_audio(bytes(audio_bytes), "ogg")
        await update.message.reply_text(f"📝 Transcripción: _{transcription}_", parse_mode="Markdown")

        cats = get_categories(uid)
        tx   = extract_transaction(transcription, cats)
        context.user_data["pending_tx"] = tx
        await update.message.reply_text(
            f"Detecté esta transacción:\n\n{_fmt_tx(tx, cats)}\n\n¿Confirmás?",
            reply_markup=CONFIRM_KB,
        )
        return CONFIRM_TX
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error al procesar el audio: {e}", reply_markup=MENU_KB)
        return MAIN_MENU


# ──────────────────────────────────────────────
# Confirmación
# ──────────────────────────────────────────────

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    uid  = _uid(context)

    if text == "✅ Confirmar":
        tx = context.user_data.get("pending_tx", {})
        try:
            add_transaction(
                user_id     = uid,
                type        = tx.get("type", "expense"),
                amount      = float(tx.get("amount", 0)),
                category_id = int(tx.get("category_id", 1)),
                description = tx.get("description", "Desde Telegram"),
                date        = tx.get("date", datetime.now().strftime("%Y-%m-%d")),
            )
            await update.message.reply_text(
                "✅ ¡Transacción guardada exitosamente!", reply_markup=MENU_KB)
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error al guardar: {e}", reply_markup=MENU_KB)

    else:
        await update.message.reply_text(
            "❌ Transacción cancelada.", reply_markup=MENU_KB)

    context.user_data.pop("pending_tx", None)
    context.user_data.pop("mode", None)
    return MAIN_MENU


# ──────────────────────────────────────────────
# Cancelar / fallback
# ──────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Conversación cancelada. Usá /start para comenzar de nuevo.",
        reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "No entendí ese mensaje. Usá /start para comenzar.", reply_markup=MENU_KB)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def build_app() -> Application:
    """Construye y devuelve la app del bot sin iniciarla. Usada por app.py."""
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado en el .env")

    application = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_username)],
            ASK_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_password)],
            MAIN_MENU: [
                MessageHandler(filters.VOICE, voice_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler),
            ],
            CONFIRM_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv)
    application.add_handler(MessageHandler(filters.ALL, unknown))
    return application


def main():
    """Entrada directa: python bot.py"""
    application = build_app()
    logger.info("Bot iniciado. Presioná Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()